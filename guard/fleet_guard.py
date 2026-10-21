#!/usr/bin/env python3
"""Fleet guard v4 (v3 + window ledger): token-free usage watchdog + Claude→GLM handoff for a Herdr fleet.

Sources (no model calls):
  * Claude account windows (five_hour / seven_day) from the per-session statusline
    snapshots ~/.claude/statusline-snapshots/<session>.json (written by
    ~/.claude/statusline-command.sh); also every agent's context_window %.
  * Z.AI windows from https://api.z.ai/api/monitor/usage/quota/limit (key read from
    ~/.claude_token_zai at call time; never printed or logged).

Behaviour:
  Claude window >= THRESHOLD  ->  PAUSE every working `ri-*` agent (Esc). Then HAND OFF:
      FIRST the commander (`--commander-agent`, default ri-commander) to `glm-commander`
      (split of its pane, cwd = --commander-cwd, protocol in <fleet-dir>/briefs/commander.md),
      THEN each paused lane to a GLM-5.3 agent `glm-<lane>` in a split of the lane's pane,
      same worktree; GLM agents commit with a "[glm-handoff]" subject prefix.
  Z.AI window >= THRESHOLD    ->  PAUSE every working `glm-*` agent until the Z.AI reset,
      then resume them.
  Claude window reset         ->  HAND BACK: lanes first, the GLM commander LAST (each commits,
      logs and exits; its pane is closed); each paused `ri-*` agent resumes with a note to
      review the GLM commits; the Claude commander gets ONE combined RESUME message (lane
      summary, integration-branch commit count, "read the GLM commander log", and any
      glm-* agents the GLM commander started, which are left running).
  Window ledger (v4)          ->  <commander-cwd>/<fleet-dir>/LEDGER.yaml (read-only for the guard; commanders
      write it). At a claude->glm handoff: ready+glm-executable+auto-start+unowned `kind: lane` items with a
      brief are started as GLM lanes (max 2 per window); ready glm-executable commander-task/review/
      evidence-prep items go in the glm-commander startup message; decisions and providers:[claude] items
      are never started or offered. RESUME lists ready claude-only items + a ledger delta. Unreadable ledger
      (no PyYAML, missing/bad file) => logged once, v3 behaviour.
  Context checkpoints         ->  an `ri-*`/`glm-*` agent whose context window crosses
      --ctx-threshold gets one "CONTEXT CHECKPOINT" prompt (re-armed after a drop of 30 points).

Deterministic log on stdout + events.jsonl. --dry-run logs herdr mutations instead of
executing them (for tests).
"""
import argparse, glob, json, os, shutil, subprocess, sys, time, urllib.request
from datetime import datetime, timezone

HOME = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(HOME, ".claude", "statusline-snapshots")
STATE_DIR = os.path.join(HOME, ".claude", "fleet-guard")
MODELS_FILE = os.path.join(SCRIPT_DIR, "models.txt")  # relaunch model map; the commander appends lanes
ZAI_TOKEN_FILE = os.path.join(HOME, ".claude_token_zai")
ZAI_QUOTA_URL = "https://api.z.ai/api/monitor/usage/quota/limit"
ZAI_BASE_URL = "https://api.z.ai/api/anthropic"
FLAG = os.path.join(STATE_DIR, "PAUSED")          # exists ⇔ Claude lanes paused
STATE = os.path.join(STATE_DIR, "state.json")
EVENTS = os.path.join(STATE_DIR, "events.jsonl")
DRY = False
MAX_AUTOSTART = 2                                   # ledger lane auto-starts per Claude window
OFFER_KINDS = ("commander-task", "review", "evidence-prep")
CARRY_KEYS = ("zai_paused", "zai_wake_at", "glm_paused", "ctx_sent")  # survive a Claude resume


def set_state_dir(path):
    global STATE_DIR, FLAG, STATE, EVENTS
    STATE_DIR = path
    FLAG, STATE, EVENTS = (os.path.join(path, n) for n in ("PAUSED", "state.json", "events.jsonl"))


def now():
    return time.time()


def ts(t=None):
    return datetime.fromtimestamp(t if t is not None else now(), timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def emit(kind, **kw):
    rec = {"t": ts(), "event": kind, **kw}
    print(f"{rec['t']}  {kind:<9} " + "  ".join(f"{k}={v}" for k, v in kw.items()), flush=True)
    with open(EVENTS, "a") as f:
        f.write(json.dumps(rec) + "\n")


def herdr(*args, timeout=60, mutate=True):
    if DRY and mutate:
        emit("dry-run", cmd="herdr " + " ".join(a if len(a) < 60 else a[:57] + "..." for a in args))
        return {}
    try:
        out = subprocess.run(["herdr", *args], capture_output=True, text=True, timeout=timeout)
        s = out.stdout.strip() or out.stderr.strip()
        return json.loads(s) if s.startswith("{") else {}
    except Exception as e:  # never crash on a transient herdr error
        emit("herdr-err", cmd=" ".join(args[:3]), err=str(e)[:120])
        return {}


def agents(prefix):
    res = herdr("agent", "list", mutate=False).get("result", {}).get("agents", [])
    return [a for a in res if (a.get("name") or "").startswith(prefix)]


def git_head(path):
    try:
        return subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def commits_since(path, base):
    """Number of commits in base..HEAD of the repo at path (0 on any problem)."""
    head = git_head(path)
    if not (base and head and head != base):
        return 0
    try:
        return len(subprocess.run(["git", "-C", path, "rev-list", f"{base}..{head}"],
                                  capture_output=True, text=True, timeout=20).stdout.split())
    except Exception:
        return 0


# --- usage sources -------------------------------------------------------------------

def claude_usage(commander_session):
    files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")), key=os.path.getmtime, reverse=True)
    usage, ctx, mtime, contexts = None, None, None, {}
    for f in files:
        try:
            d = json.load(open(f))
        except Exception:
            continue
        sid = d.get("session_id")
        cw = (d.get("context_window") or {}).get("used_percentage")
        if sid and cw is not None and now() - os.path.getmtime(f) < 3600:  # snapshots older than 1 h are ignored
            contexts[sid] = cw
        if usage is None and d.get("rate_limits"):
            usage, mtime = d["rate_limits"], os.path.getmtime(f)
        if sid and sid == commander_session:
            ctx = cw
    windows = {}
    for name in ("five_hour", "seven_day"):
        w = (usage or {}).get(name) or {}
        if w.get("used_percentage") is not None:
            windows[name] = (w["used_percentage"], w.get("resets_at"))
    return windows, mtime, ctx, contexts


def zai_usage():
    try:
        tok = open(ZAI_TOKEN_FILE).read().strip()
        req = urllib.request.Request(ZAI_QUOTA_URL, headers={"Authorization": f"Bearer {tok}"})
        d = json.load(urllib.request.urlopen(req, timeout=15))
        out = {}
        for lim in (d.get("data") or {}).get("limits") or []:
            unit, num = lim.get("unit"), lim.get("number")
            name = {(3, 5): "zai_5h", (6, 1): "zai_week"}.get((unit, num), f"zai_u{unit}n{num}")
            out[name] = (lim.get("percentage"), (lim.get("nextResetTime") or 0) / 1000)
        return out
    except Exception as e:
        return {"error": str(e)[:80]}


def tripped(windows, threshold):
    """(name, reset_at, pct) of the tripped window that resets last, or None.
    A window whose reset already passed is stale data and never trips."""
    trip = None
    for name, (pct, reset) in windows.items():
        if pct is not None and pct >= threshold and reset and reset > now():
            if trip is None or reset > trip[1]:
                trip = (name, reset, pct)
    return trip


# --- state ---------------------------------------------------------------------------

def save_state(st):
    with open(STATE + ".tmp", "w") as f:
        json.dump(st, f, indent=1)
    os.replace(STATE + ".tmp", STATE)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except Exception:
        return {}


def fresh_state(old):
    return {"resumed_at": old.get("resumed_at", 0), **{k: old[k] for k in CARRY_KEYS if k in old}}


def reset_state():
    """Archive state.json, PAUSED and events.jsonl into archive/<YYYY-MM-DD-HHMMSS>/ and start clean."""
    dest = os.path.join(STATE_DIR, "archive", datetime.fromtimestamp(now()).strftime("%Y-%m-%d-%H%M%S"))
    moved = []
    for p in (STATE, FLAG, EVENTS):
        if os.path.exists(p):
            os.makedirs(dest, exist_ok=True)
            shutil.move(p, os.path.join(dest, os.path.basename(p)))
            moved.append(os.path.basename(p))
    return dest, moved


# --- actions -------------------------------------------------------------------------

def pause_working(prefix):
    hit = []
    for a in agents(prefix):
        if a.get("agent_status") == "working":
            herdr("agent", "send-keys", a["name"], "esc")
            hit.append(a["name"])
    return hit


def set_lead(cwd, role, holder):
    """Lane-lead signal: <worktree>/.lane-lead names the only role allowed to modify files
    (enforced by ~/.claude/fleet-guard/lead_hook.sh; git-excluded)."""
    if DRY:
        emit("dry-run", cmd=f"lead {cwd} -> {role}:{holder}")
        return
    try:
        p = os.path.join(cwd, ".lane-lead")
        with open(p + ".tmp", "w") as f:
            json.dump({"role": role, "holder": holder, "since": ts()}, f)
        os.replace(p + ".tmp", p)
        emit("LEAD", worktree=os.path.basename(cwd), role=role, holder=holder)
    except Exception as e:
        emit("lead-err", worktree=cwd, err=str(e)[:100])


def start_glm(pane, cwd, name, args, prompt):
    """Split `pane` (cwd = cwd), start a GLM claude agent `name` in it and send `prompt`.
    Returns (glm_pane, base_commit) or (None, '')."""
    split = herdr("pane", "split", pane, "--direction", "right", "--cwd", cwd, "--no-focus")
    gpane = (split.get("result") or {}).get("pane", {}).get("pane_id") or ("DRY-PANE" if DRY else None)
    if not gpane:
        return None, ""
    base = start_in_pane(gpane, cwd, name, args, prompt)
    return gpane, base


def start_in_pane(gpane, cwd, name, args, prompt):
    """Credentials + lead + agent start + prompt in an existing shell pane. Returns the cwd's HEAD."""
    # credentials enter the pane's shell from the file; the key never appears in argv or logs
    herdr("pane", "run", gpane,
          f'export RI_ROLE=glm ANTHROPIC_BASE_URL={ZAI_BASE_URL} ANTHROPIC_AUTH_TOKEN="$(cat {ZAI_TOKEN_FILE})" '
          f'ANTHROPIC_SMALL_FAST_MODEL={args.glm_model}')
    set_lead(cwd, "glm", name)
    time.sleep(2)
    herdr("agent", "start", name, "--kind", "claude", "--pane", gpane, "--timeout", "90000", "--",
          "--model", args.glm_model, "--permission-mode", "bypassPermissions", timeout=120)
    base = git_head(cwd)
    herdr("agent", "prompt", name, prompt)
    return base


def glm_name(args, claude_agent):
    return (args.glm_prefix + claude_agent[len(args.prefix):])[:32]


def handoff(lane_agent, st, args):
    """Start glm-<lane> next to the paused Claude lane agent, in its worktree."""
    lane = lane_agent[len(args.prefix):]
    name = glm_name(args, lane_agent)
    info = next((a for a in agents(args.prefix) if a.get("name") == lane_agent), None)
    if not info:
        emit("handoff-skip", lane=lane, why="agent not found")
        return
    if info.get("agent_status") == "working":  # lead moves only once the Claude agent has stopped
        emit("handoff-wait", lane=lane, why="claude agent still working")
        return
    cwd, pane = info.get("cwd"), info.get("pane_id")
    fd = args.fleet_dir
    prompt = (f"You are '{name}', a GLM-5.3 agent temporarily continuing the '{lane}' lane of a multi-agent build "
              f"fleet while its Claude agent is paused for a usage-limit window. Your working directory is that "
              f"lane's git worktree (branch: see `git branch --show-current`). Read {fd}/FLEET.md "
              f"(binding rules), then {fd}/briefs/{lane}.md and the lane's status file "
              f"{fd}/status/{lane}.md, then `git status` and `git log --oneline -15`, and continue "
              f"the lane's remaining work from where it stopped. Rules: commit small and often; EVERY commit subject "
              f"starts with '[glm-handoff] '; you hold the lane lead (.lane-lead) — never edit that file; never merge, rebase, push or touch other worktrees; add a 'GLM handoff log' "
              f"section to the status file describing what you did and anything uncertain. When you receive a message "
              f"starting 'HANDBACK', stop, commit all work, update the log, and reply 'HANDBACK DONE'.")
    gpane, base = start_glm(pane, cwd, name, args, prompt)
    if not gpane:
        emit("handoff-fail", lane=lane, why="pane split failed")
        return
    st.setdefault("handoff", {})[lane_agent] = {"agent": name, "pane": gpane, "cwd": cwd, "base": base,
                                                "started_at": now()}
    emit("HANDOFF", lane=lane, glm_agent=name, pane=gpane, base=base[:9])


def handoff_commander(st, args):
    """Hand the commander to glm-commander (before any lane). Recorded in st['commander']."""
    if st.get("commander"):
        return
    cname = args.commander_agent
    info = next((a for a in agents(args.prefix) if a.get("name") == cname), None)
    if not info:
        emit("handoff-skip", lane="commander", why="agent not found")
        st["commander"] = {"skipped": True}
        return
    if not args.commander_cwd:
        emit("handoff-skip", lane="commander", why="no --commander-cwd")
        st["commander"] = {"skipped": True}
        return
    if info.get("agent_status") == "working":
        emit("handoff-wait", lane="commander", why="claude agent still working")
        return
    name = glm_name(args, cname)
    fd = args.fleet_dir
    prompt = (f"You are {name}, temporarily commanding the env-impact fleet while the Claude commander is paused "
              f"for a usage window. Read {fd}/FLEET.md, {fd}/briefs/commander.md (follow its **GLM commander "
              f"protocol** exactly) and {fd}/COMMANDER.md, then continue. On a message starting 'HANDBACK', follow "
              f"the protocol's handback steps and reply 'HANDBACK DONE'.") + ledger_offer_text(args)
    gpane, base = start_glm(info.get("pane_id"), args.commander_cwd, name, args, prompt)
    if not gpane:
        emit("handoff-fail", lane="commander", why="pane split failed")
        return
    if cname not in st.get("paused", []):
        st.setdefault("paused", []).append(cname)
    st["workspace"] = info.get("workspace_id") or args.workspace
    st["commander"] = {"agent": name, "pane": gpane, "cwd": args.commander_cwd, "base": base, "started_at": now()}
    emit("HANDOFF", lane="commander", glm_agent=name, pane=gpane, base=base[:9])


def close_glm(h, args, zai_paused, message):
    """Ask the GLM agent to wrap up (unless Z.AI-paused), exit it, close its pane."""
    name = h["agent"]
    if not zai_paused:
        herdr("agent", "prompt", name, message)
        herdr("agent", "wait", name, "--timeout", str(args.handback_timeout * 1000), timeout=args.handback_timeout + 30)
    herdr("agent", "send-keys", name, "esc")
    herdr("agent", "prompt", name, "/exit")
    time.sleep(3)
    herdr("pane", "close", h["pane"])  # kills the GLM process; only then does the lead move back


def handback(st, args, zai_paused):
    """Hand every registered lane back. Returns [(lane_agent, handoff_info, glm_commits)]."""
    summary = []
    for lane_agent, h in sorted((st.get("handoff") or {}).items()):
        close_glm(h, args, zai_paused, "HANDBACK: the Claude agent is resuming this lane. Stop now: commit all "
                  "work with the '[glm-handoff] ' prefix, update the GLM handoff log in the status file, reply 'HANDBACK DONE'.")
        set_lead(h["cwd"], "claude", lane_agent)
        n = commits_since(h["cwd"], h.get("base"))
        summary.append((lane_agent, h, n))
        emit("HANDBACK", lane=lane_agent, glm_agent=h["agent"], glm_commits=n)
    return summary


def handback_commander(st, args, zai_paused):
    """Hand the commander back (call after the lanes). Returns (info, commits) or None."""
    c = st.get("commander")
    if not c or c.get("skipped"):
        return None
    close_glm(c, args, zai_paused, "HANDBACK: the Claude commander is resuming. Follow the handback steps of the GLM "
              "commander protocol in briefs/commander.md (no half-merged state, commit, final GLM commander log entry), "
              "then reply exactly 'HANDBACK DONE'.")
    set_lead(c["cwd"], "claude", args.commander_agent)
    n = commits_since(c["cwd"], c.get("base"))
    emit("HANDBACK", lane="commander", glm_agent=c["agent"], glm_commits=n)
    return c, n


def commander_resume_msg(args, st, summary, cres, leftovers):
    extra = ledger_resume_text(st, args)
    lanes = ", ".join(f"{la}→{h['agent']} ({n} commits)" for la, h, n in summary) or "none"
    msg = (f"RESUME (fleet guard): the Claude {st.get('window')} usage window has reset. You are commanding the "
           f"fleet again; run `git status` first. Lane handbacks: {lanes}.")
    if cres:
        c, n = cres
        msg += (f" While you were paused, {c['agent']} commanded the fleet: {n} commit(s) on the integration branch "
                f"(`git log {c['base'][:12]}..HEAD`, subjects start with '[glm-handoff]').")
    if cres:
        msg += (" Read the 'GLM commander log' in COMMANDER.md and review every [glm-handoff] merge critically (re-run "
                "build/vet/tests; revert if wrong) before continuing from 'Next actions'.")
    else:
        msg += " The commander was not handed off to GLM; continue from 'Next actions' in COMMANDER.md."
    if leftovers:
        msg += (" glm-* agents NOT started by the guard are still running (not closed): "
                + ", ".join(leftovers) + ". Decide whether each continues under GLM or moves to a Claude agent.")
    return msg + extra


# --- window ledger (v4) ---------------------------------------------------------------

def run_git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout or r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def load_ledger(a):
    """(ledger_dict, None) or (None, reason). Fails soft: anything wrong => unreadable."""
    if not a.commander_cwd:
        return None, "no --commander-cwd"
    path = os.path.join(a.commander_cwd, a.fleet_dir, "LEDGER.yaml")
    try:
        import yaml
        with open(path) as f:
            d = yaml.safe_load(f)
        if not isinstance(d, dict) or not isinstance(d.get("items"), list):
            raise ValueError("no items list")
        return d, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:80]}"


def ledger_items(d):
    return [i for i in d["items"] if isinstance(i, dict) and i.get("id")]


def _by_id(d):
    return {str(i["id"]): i for i in ledger_items(d)}


def is_ready(item, by_id):
    """status ready AND every dependency exists and is done."""
    if item.get("status") != "ready":
        return False
    return all((by_id.get(str(x)) or {}).get("status") == "done" for x in (item.get("depends") or []))


def glm_ok(item):
    """Enqueue-time GLM authorization: glm-executable true, glm among providers, never a decision."""
    return (item.get("glm-executable") is True and "glm" in (item.get("providers") or [])
            and item.get("kind") != "decision")


def ledger_offered(d):
    by = _by_id(d)
    return [i for i in ledger_items(d) if is_ready(i, by) and glm_ok(i) and not i.get("owner")
            and i.get("kind") in OFFER_KINDS]


def ledger_autostartable(d, a):
    by = _by_id(d)
    out = []
    for i in ledger_items(d):
        brief = str(i.get("brief") or "").split("#")[0]
        if (i.get("kind") == "lane" and is_ready(i, by) and glm_ok(i) and i.get("auto-start") is True
                and not i.get("owner") and brief
                and os.path.isfile(os.path.join(a.commander_cwd, a.fleet_dir, brief))):
            out.append(i)
    return out


def ledger_claude_ready(d):
    by = _by_id(d)
    return [i for i in ledger_items(d) if is_ready(i, by) and set(i.get("providers") or []) == {"claude"}]


def ledger_delta(baseline, d):
    out = []
    for i in ledger_items(d):
        iid, cur = str(i["id"]), [i.get("status"), i.get("owner") or ""]
        old = baseline.get(iid)
        if old is None:
            out.append(f"{iid} new ({cur[0]})")
        elif old != cur:
            out.append(f"{iid} {old[0]}→{cur[0]}" + (f" owner {old[1] or '-'}→{cur[1] or '-'}" if old[1] != cur[1] else ""))
    return out


def lane_name_for(item):
    stem = os.path.splitext(os.path.basename(str(item.get("brief") or "").split("#")[0]))[0] or str(item["id"])
    lane = "".join(c if c.isalnum() or c in "_-" else "-" for c in stem.lower()).strip("-_") or "lane"
    return lane if lane[0].isalpha() else "w" + lane


def ledger_snapshot(st, a):
    """Once per window: read the ledger, remember each item's (status, owner) as the delta baseline."""
    if st.get("ledger") is not None:
        return
    d, err = load_ledger(a)
    lg = {"baseline": {}, "autostarted": {}, "count": 0, "unreadable": d is None, "done": False}
    if d is None:
        emit("ledger", status="unreadable", why=err)
    else:
        lg["baseline"] = {str(i["id"]): [i.get("status"), i.get("owner") or ""] for i in ledger_items(d)}
        emit("ledger", status="read", items=len(ledger_items(d)),
             offered=",".join(str(i["id"]) for i in ledger_offered(d)) or "-",
             autostart=",".join(str(i["id"]) for i in ledger_autostartable(d, a)) or "-")
    st["ledger"] = lg


def ledger_offer_text(a):
    """Startup-message addendum for glm-commander ('' when nothing offered or ledger unreadable)."""
    d, _ = load_ledger(a)
    if d is None:
        return ""
    items = ledger_offered(d)
    if not items:
        return ""
    lines = "; ".join(f"{i['id']} [{i.get('kind')}] {i.get('title', '')}" for i in items)
    return (f" LEDGER ({a.fleet_dir}/LEDGER.yaml): these items are ready and pre-authorized for GLM "
            f"(glm-executable) — you may execute them: {lines}. Set each item's status/owner as it moves and "
            f"record it in this window's `windows:` entry. Execute ONLY items with glm-executable: true; never a "
            f"kind: decision item and never a providers: [claude] item.")


def make_lane_worktree(a, lane):
    """Create (or reuse) <worktrees>/<prefix>-<lane> on branch <prefix>/<lane> from the integration branch."""
    branch, wt = f"{a.lane_prefix}/{lane}", os.path.join(os.path.dirname(a.commander_cwd.rstrip("/")), f"{a.lane_prefix}-{lane}")
    if os.path.isdir(wt):
        return wt, branch
    if DRY:
        emit("dry-run", cmd=f"git worktree add -b {branch} {wt}")
        return wt, branch
    base = a.integration_branch or run_git(a.commander_cwd, "branch", "--show-current")[1]
    rc, out = run_git(a.commander_cwd, "worktree", "add", "-b", branch, wt, base)
    if rc != 0:  # branch may already exist
        rc, out = run_git(a.commander_cwd, "worktree", "add", wt, branch)
    if rc != 0:
        emit("autostart-fail", lane=lane, why=out[:100])
        return None, branch
    return wt, branch


def ledger_autostart(st, a, workspace):
    """Start up to MAX_AUTOSTART eligible ledger lanes as GLM agents. Does NOT write the ledger."""
    lg = st.get("ledger")
    if not lg or lg.get("unreadable") or lg.get("done") or not st.get("commander"):
        return
    lg["done"] = True
    d, err = load_ledger(a)
    if d is None:
        emit("ledger", status="unreadable", why=err)
        return
    live = {x.get("name") for x in agents(a.glm_prefix)}
    fd = a.fleet_dir
    for item in ledger_autostartable(d, a):
        iid = str(item["id"])
        if lg["count"] >= MAX_AUTOSTART:
            emit("autostart-skip", item=iid, why=f"cap {MAX_AUTOSTART} per window")
            continue
        lane = lane_name_for(item)
        name = (a.glm_prefix + lane)[:32]
        if name in live or iid in lg["autostarted"]:
            continue
        wt, branch = make_lane_worktree(a, lane)
        if not wt:
            continue
        tab = herdr("tab", "create", "--workspace", workspace, "--cwd", wt, "--label", name, "--no-focus")
        pane = (tab.get("result") or {}).get("root_pane", {}).get("pane_id") or ("DRY-PANE" if DRY else None)
        if not pane:
            emit("autostart-fail", item=iid, why="tab create failed")
            continue
        integ = f" Integrity: {item['integrity']}." if item.get("integrity") else ""
        brief = str(item["brief"]).split("#")[0]
        prompt = (f"You are '{name}', a GLM-5.3 agent starting the '{lane}' lane (ledger item {iid}: {item.get('title', '')}) "
                  f"in a GLM window because the item is glm-executable and auto-start. Your working directory is the "
                  f"lane's git worktree on branch {branch}. Read {fd}/FLEET.md (binding rules), then {fd}/{brief}, "
                  f"keep {fd}/status/{lane}.md current, and do the lane. Rules: commit small and often; EVERY commit "
                  f"subject starts with '[glm-handoff] ' and ends with 'Co-Authored-By: GLM-5.3 <noreply@z.ai>'; never "
                  f"merge, rebase, push or touch other worktrees; do not edit LEDGER.yaml (the commander does).{integ} "
                  f"Finish with a final message starting 'LANE DONE:'.")
        start_in_pane(pane, wt, name, a, prompt)
        lg["autostarted"][iid] = name
        lg["count"] += 1
        emit("AUTOSTART", item=iid, glm_agent=name, branch=branch, worktree=os.path.basename(wt), pane=pane)
    if lg["autostarted"] and (st.get("commander") or {}).get("agent"):
        started = ", ".join(f"{n} (ledger {i})" for i, n in lg["autostarted"].items())
        herdr("agent", "prompt", st["commander"]["agent"],
              f"FLEET GUARD: auto-started GLM lanes from the ledger: {started}. Set each item's status: in-progress "
              f"and owner in LEDGER.yaml and track them (the guard never writes the ledger).")


def ledger_resume_text(st, a):
    """RESUME addendum: ready claude-only items + ledger delta + guard auto-starts ('' if unreadable)."""
    lg = st.get("ledger") or {}
    d, err = load_ledger(a) if not lg.get("unreadable") else (None, "unreadable at handoff")
    if d is None:
        return ""
    parts = []
    ready = ledger_claude_ready(d)
    if ready:
        parts.append(" Ledger items ready for YOU (providers: [claude]; GLM never executes these): "
                     + "; ".join(f"{i['id']} [{i.get('kind')}"
                                 + (f", decision-rights {i['decision-rights']}" if i.get("decision-rights") else "")
                                 + f"] {i.get('title', '')}" for i in ready) + ".")
    delta = ledger_delta(lg.get("baseline") or {}, d) if lg.get("baseline") else []
    if delta:
        parts.append(" Ledger delta during the window: " + "; ".join(delta) + ".")
    if lg.get("autostarted"):
        parts.append(" Guard auto-started (still running, not closed): "
                     + ", ".join(f"{n} ({i})" for i, n in lg["autostarted"].items()) + ".")
    return "".join(parts)


def context_checkpoints(st, args, contexts):
    """One CONTEXT CHECKPOINT prompt per threshold crossing; re-armed after a drop below threshold-30."""
    sent = st.setdefault("ctx_sent", {})
    for prefix in (args.prefix, args.glm_prefix):
        for a in agents(prefix):
            name = a.get("name")
            sid = (a.get("agent_session") or {}).get("value")
            pct = contexts.get(sid) if sid else None
            if pct is None:
                continue
            if name in sent:
                if pct < args.ctx_threshold - 30:
                    del sent[name]
                    emit("CTX", agent=name, ctx=f"{pct}%", action="re-armed")
                continue
            if pct < args.ctx_threshold:
                continue
            claude_paused = os.path.exists(FLAG) and prefix == args.prefix
            if claude_paused or (prefix == args.glm_prefix and st.get("zai_paused")):
                continue  # a prompt would wake a paused agent and burn the exhausted window
            herdr("agent", "prompt", name,
                  f"CONTEXT CHECKPOINT (fleet guard): your context window is at {int(pct)}%. Update and commit your "
                  f"status file now (commander: COMMANDER.md) so work survives compaction, then continue.")
            sent[name] = pct
            emit("CTX", agent=name, ctx=f"{int(pct)}%", action="checkpoint-sent")


def load_models():
    models = {}
    try:
        with open(MODELS_FILE) as f:
            for line in f:
                if len(line.split()) >= 2:
                    models[line.split()[0]] = line.split()[1]
    except Exception:
        pass
    return models


# --- main loop -----------------------------------------------------------------------

def new_loop():
    return {"last": None, "last_zai": None, "zai_at": 0, "zai": {}}


def step(st, a, lp):
    """One iteration of the guard loop. Returns (state, seconds_to_sleep)."""
    windows, mtime, ctx, contexts = claude_usage(a.commander_session)
    if now() - lp["zai_at"] >= a.zai_interval:
        lp["zai"], lp["zai_at"] = zai_usage(), now()
    zai = lp["zai"]
    sample = (tuple(sorted(windows.items())), ctx)
    if sample != lp["last"]:
        emit("claude", **{k: f"{p}%" for k, (p, _) in windows.items()},
             five_hour_reset=ts(windows["five_hour"][1]) if windows.get("five_hour", (0, 0))[1] else "?",
             commander_ctx=f"{ctx}%", snapshot_age_s=int(now() - mtime) if mtime else None)
        lp["last"] = sample
    zs = tuple(sorted((k, v if k == "error" else v[0]) for k, v in zai.items()))
    if zs != lp["last_zai"]:
        emit("zai", **{k: (v if k == "error" else f"{v[0]}% reset {ts(v[1])}") for k, v in zai.items()})
        lp["last_zai"] = zs

    # ---- Z.AI side: pause / resume GLM agents ----------------------------------------
    zwin = {k: v for k, v in zai.items() if k != "error"}
    if not st.get("zai_paused"):
        zt = tripped(zwin, a.zai_threshold)
        if zt:
            st.update(zai_paused=True, zai_wake_at=zt[1] + a.buffer, glm_paused=pause_working(a.glm_prefix))
            save_state(st)
            emit("ZAI-PAUSE", window=zt[0], used=f"{zt[2]}%", agents=",".join(st["glm_paused"]) or "-",
                 wake_at=ts(st["zai_wake_at"]))
    elif now() >= st.get("zai_wake_at", 0):
        for n in st.get("glm_paused", []):
            herdr("agent", "prompt", n, "RESUME (fleet guard): the Z.AI usage window reset. Continue where you left off.")
        emit("ZAI-RESUME", agents=",".join(st.get("glm_paused", [])) or "-")
        st.update(zai_paused=False, zai_wake_at=0, glm_paused=[])
        save_state(st)
    else:
        hit = pause_working(a.glm_prefix)
        if hit:
            st["glm_paused"] = sorted(set(st.get("glm_paused", [])) | set(hit))
            save_state(st)

    # ---- context checkpoints ---------------------------------------------------------
    before = json.dumps(st.get("ctx_sent"), sort_keys=True)
    context_checkpoints(st, a, contexts)
    if json.dumps(st.get("ctx_sent"), sort_keys=True) != before:
        save_state(st)

    # ---- Claude side -----------------------------------------------------------------
    if not os.path.exists(FLAG):
        fresh = mtime is not None and mtime > st.get("resumed_at", 0)
        trip = tripped(windows, a.threshold) if fresh else None
        if trip:
            with open(FLAG, "w") as f:
                f.write(f"{trip[0]} {trip[2]}%\n")
            st.update(window=trip[0], pct=trip[2], wake_at=trip[1] + a.buffer, paused_at=now(),
                      paused=pause_working(a.prefix), handoff={}, commander=None, ledger=None)
            save_state(st)
            emit("PAUSE", window=trip[0], used=f"{trip[2]}%", agents=",".join(st["paused"]) or "-",
                 wake_at=ts(st["wake_at"]))
        return st, a.interval

    if now() < st.get("wake_at", 0):
        hit = pause_working(a.prefix)
        if hit:
            st["paused"] = sorted(set(st.get("paused", [])) | set(hit))
            emit("enforce", re_paused=",".join(hit))
        esc = st.setdefault("esc_count", {})
        for n in hit:
            esc[n] = esc.get(n, 0) + 1
            if esc[n] >= 3:  # background sub-agents keep it working: end the session, resume later
                info = (herdr("agent", "get", n, mutate=False).get("result") or {}).get("agent") or {}
                sid = (info.get("agent_session") or {}).get("value")
                if sid:
                    st.setdefault("relaunch", {})[n] = {"session": sid, "pane": info.get("pane_id")}
                    herdr("agent", "send-keys", n, "ctrl+c")
                    herdr("agent", "send-keys", n, "ctrl+c")
                    emit("EXITED", agent=n, session=sid, why="still working after 3 Esc (background sub-agents)")
                esc[n] = -999
        if not a.no_handoff and not st.get("zai_paused") and "error" not in zai:
            ledger_snapshot(st, a)
            handoff_commander(st, a)  # commander first, lanes after
            for lane_agent in list(st.get("paused", [])):
                if lane_agent != a.commander_agent and lane_agent not in (st.get("handoff") or {}):
                    handoff(lane_agent, st, a)
            ledger_autostart(st, a, st.get("workspace") or a.workspace)
        save_state(st)
        return st, min(a.interval, max(5, st["wake_at"] - now()))

    # ---- Claude window reset: hand back (lanes, then commander), resume ------------------
    zp = st.get("zai_paused", False)
    summary = handback(st, a, zp)
    cres = handback_commander(st, a, zp)
    models = load_models()
    for n, r in (st.get("relaunch") or {}).items():
        herdr("agent", "start", n, "--kind", "claude", "--pane", r["pane"], "--timeout", "90000", "--",
              "--resume", r["session"], "--model", models.get(n, "claude-opus-5-5"),
              "--permission-mode", "bypassPermissions", timeout=120)
        emit("RELAUNCH", agent=n, session=r["session"], model=models.get(n, "claude-opus-5-5"))
    registered = {h["agent"] for _, h, _ in summary} | ({cres[0]["agent"]} if cres else set())
    registered |= set(((st.get("ledger") or {}).get("autostarted") or {}).values())
    leftovers = sorted(x["name"] for x in agents(a.glm_prefix) if x.get("name") not in registered)
    glm_note = {la: (h, n) for la, h, n in summary}
    paused = st.get("paused", [])
    for name in [x for x in paused if x != a.commander_agent]:
        msg = ("RESUME (fleet guard): the Claude usage window has reset. Continue your lane exactly where you "
               "left off; run `git status` first.")
        if name in glm_note:
            h, n = glm_note[name]
            msg += (f" While you were paused, a GLM-5.3 agent ({h['agent']}) continued this lane in your worktree: "
                    f"{n} commit(s) in `git log {h['base'][:12]}..HEAD` (subjects start with '[glm-handoff]'), plus any "
                    f"uncommitted changes and a 'GLM handoff log' in your status file. Review that work critically "
                    f"before building on it — fix or revert anything wrong — then continue.")
        herdr("agent", "prompt", name, msg)
    if a.commander_agent in paused or cres:  # single combined message; replaces v2's commander-pane wake prompt
        herdr("agent", "prompt", a.commander_agent, commander_resume_msg(a, st, summary, cres, leftovers))
    os.remove(FLAG)
    emit("RESUME", agents=",".join(paused) or "-", glm_commits=sum(n for _, _, n in summary) + (cres[1] if cres else 0),
         unregistered_glm=",".join(leftovers) or "-")
    st = fresh_state({**st, "resumed_at": now()})
    save_state(st)
    lp["last"] = None
    return st, 0


def build_parser():
    ap = argparse.ArgumentParser(description="Fleet guard v3 (see README-guard.md)")
    ap.add_argument("--commander-pane", default="", help="deprecated (v2); ignored")
    ap.add_argument("--commander-session", default="", help="session id of the commander, for its ctx % in the log")
    ap.add_argument("--commander-agent", default="ri-commander")
    ap.add_argument("--commander-cwd", default="", help="integration worktree; required unless --no-handoff")
    ap.add_argument("--fleet-dir", default="docs/phase4/env-impact")
    ap.add_argument("--lane-prefix", default="p5ll", help="ledger auto-start lanes: branch <p>/<lane>, worktree <p>-<lane>")
    ap.add_argument("--integration-branch", default="", help="base for auto-start lane branches (default: commander-cwd's branch)")
    ap.add_argument("--workspace", default="w1", help="herdr workspace for auto-start lane tabs")
    ap.add_argument("--prefix", default="ri-")
    ap.add_argument("--glm-prefix", default="glm-")
    ap.add_argument("--glm-model", default="glm-5.3")
    ap.add_argument("--threshold", type=float, default=90.0)
    ap.add_argument("--zai-threshold", type=float, default=90.0)
    ap.add_argument("--ctx-threshold", type=float, default=80.0)
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--zai-interval", type=int, default=120)
    ap.add_argument("--buffer", type=int, default=90)
    ap.add_argument("--handback-timeout", type=int, default=600)
    ap.add_argument("--state-dir", default="", help="override state/log dir (tests, dry runs)")
    ap.add_argument("--reset-state", action="store_true", help="archive state.json/PAUSED/events.jsonl and start clean")
    ap.add_argument("--no-handoff", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    return ap


def main():
    global DRY
    ap = build_parser()
    a = ap.parse_args()
    if not a.no_handoff and not a.commander_cwd:
        ap.error("--commander-cwd is required unless --no-handoff")
    DRY = a.dry_run
    if a.state_dir:
        set_state_dir(os.path.abspath(a.state_dir))
    os.makedirs(STATE_DIR, exist_ok=True)
    if a.reset_state:
        dest, moved = reset_state()
        emit("reset", archived=",".join(moved) or "-", to=dest)

    st = load_state()
    if os.path.exists(FLAG) and st.get("wake_at"):
        emit("restore", paused=",".join(st.get("paused", [])), wake_at=ts(st["wake_at"]),
             handoffs=",".join((st.get("handoff") or {}).keys()) or "-")
    else:
        if os.path.exists(FLAG):
            os.remove(FLAG)
        st = fresh_state(st)
    emit("start", threshold=a.threshold, zai_threshold=a.zai_threshold, ctx_threshold=a.ctx_threshold,
         prefix=a.prefix, glm=f"{a.glm_prefix}* {a.glm_model}", handoff=not a.no_handoff,
         commander=a.commander_agent, fleet_dir=a.fleet_dir, dry_run=DRY)

    lp = new_loop()
    while True:
        st, delay = step(st, a, lp)
        time.sleep(delay)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        emit("stop")
        sys.exit(0)
