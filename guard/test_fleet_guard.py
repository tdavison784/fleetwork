"""Tests for fleet_guard.py v3. stdlib unittest; no network, no real herdr, no real sleeps."""
import argparse, json, os, shutil, sys, tempfile, unittest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet_guard as fg

CMD_CWD = "/wt/integration"


class FakeHerdr:
    """Records every herdr call; serves `agent list` from self.agent_list."""
    def __init__(self):
        self.calls, self.agent_list, self.n = [], [], 0

    def __call__(self, *args, timeout=60, mutate=True):
        self.calls.append(args)
        if args[:2] == ("agent", "list"):
            return {"result": {"agents": list(self.agent_list)}}
        if args[:2] == ("tab", "create"):
            self.n += 1
            return {"result": {"root_pane": {"pane_id": f"w1:pT{self.n}"}}}
        if args[:2] == ("pane", "split"):
            self.n += 1
            return {"result": {"pane": {"pane_id": f"w1:pG{self.n}"}}}
        return {}

    def find(self, *prefix):
        return [c for c in self.calls if c[:len(prefix)] == prefix]

    def prompts(self, name):
        return [c[3] for c in self.calls if c[:3] == ("agent", "prompt", name)]


def ag(name, status="idle", cwd="/wt/x", pane="w1:p1", session=None):
    d = {"name": name, "agent_status": status, "cwd": cwd, "pane_id": pane}
    if session:
        d["agent_session"] = {"value": session}
    return d


def make_args(**kw):
    a = dict(commander_pane="", commander_session="", commander_agent="fw-commander", commander_cwd=CMD_CWD,
             fleet_dir="fleet", prefix="fw-", glm_prefix="glm-", glm_model="glm-5.3",
             threshold=90.0, zai_threshold=90.0, ctx_threshold=80.0, interval=30, zai_interval=120, buffer=90,
             handback_timeout=1, no_handoff=False, dry_run=False,
             lane_prefix="lane", integration_branch="p5-int", workspace="w1")
    a.update(kw)
    return argparse.Namespace(**a)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.saved = {k: getattr(fg, k) for k in ("herdr", "git_head", "now", "claude_usage", "zai_usage",
                                                  "STATE_DIR", "FLAG", "STATE", "EVENTS", "DRY", "MODELS_FILE")}
        fg.set_state_dir(self.tmp)
        fg.DRY = False
        fg.MODELS_FILE = os.path.join(self.tmp, "models.txt")
        self.h = FakeHerdr()
        self.t = 1_000_000.0
        self.windows = {}
        self.contexts = {}
        self.zai = {}
        fg.herdr = self.h
        fg.git_head = lambda p: "base" + "0" * 36
        fg.now = lambda: self.t
        fg.claude_usage = lambda s: (self.windows, self.t - 1, None, self.contexts)
        fg.zai_usage = lambda: self.zai
        self._sleep = fg.time.sleep
        fg.time.sleep = lambda s: None
        self._stdout = sys.stdout
        sys.stdout = open(os.devnull, "w")
        self.a = make_args()
        self.lp = fg.new_loop()
        self.st = {}

    def tearDown(self):
        sys.stdout.close()
        sys.stdout = self._stdout
        fg.time.sleep = self._sleep
        for k, v in self.saved.items():
            setattr(fg, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def step(self):
        self.st, delay = fg.step(self.st, self.a, self.lp)
        return delay

    def events(self):
        try:
            return [json.loads(l) for l in open(fg.EVENTS)]
        except FileNotFoundError:
            return []

    def kinds(self):
        return [e["event"] for e in self.events()]

    def trip_claude(self, reset_in=3600):
        self.windows = {"seven_day": (95, self.t + reset_in)}

    def fleet(self, commander="idle"):
        self.h.agent_list = [ag("fw-commander", commander, CMD_CWD, "w1:p8"),
                             ag("fw-bundle", "working", "/wt/bundle", "w1:p2")]

    def settle(self):
        """After the Esc the working agents are idle."""
        for x in self.h.agent_list:
            if x["agent_status"] == "working" and x["name"].startswith("fw-"):
                x["agent_status"] = "idle"

    def go(self):
        self.step()      # trip -> PAUSE
        self.settle()
        self.step()      # enforce -> handoffs


class HandoffTests(Base):
    def test_commander_handed_off_before_lanes(self):
        self.fleet()
        self.trip_claude()
        self.go()
        starts = [c[2] for c in self.h.find("agent", "start")]
        self.assertEqual(starts, ["glm-commander", "glm-bundle"])
        splits = self.h.find("pane", "split")
        self.assertEqual(splits[0][:2], ("pane", "split"))
        self.assertEqual(splits[0][2], "w1:p8")
        self.assertEqual(splits[0][splits[0].index("--cwd") + 1], CMD_CWD)
        self.assertEqual(splits[1][splits[1].index("--cwd") + 1], "/wt/bundle")
        p = self.h.prompts("glm-commander")[0]
        self.assertIn("You are glm-commander, temporarily commanding the env-impact fleet", p)
        self.assertIn("fleet/FLEET.md", p)
        self.assertIn("fleet/briefs/commander.md", p)
        self.assertIn("fleet/COMMANDER.md", p)
        self.assertIn("HANDBACK DONE", p)
        for line in self.h.find("pane", "run"):
            self.assertIn("FLEET_ROLE=glm", line[3])
        self.assertIn("commander", [e.get("lane") for e in self.events() if e["event"] == "HANDOFF"])
        self.assertEqual(self.st["commander"]["agent"], "glm-commander")

    def test_lead_files_written(self):
        wt = os.path.join(self.tmp, "wt-cmd")
        os.makedirs(wt)
        lane = os.path.join(self.tmp, "wt-lane")
        os.makedirs(lane)
        self.a = make_args(commander_cwd=wt)
        self.h.agent_list = [ag("fw-commander", "idle", wt, "w1:p8"), ag("fw-bundle", "working", lane, "w1:p2")]
        self.trip_claude()
        self.go()
        for d in (wt, lane):
            self.assertEqual(json.load(open(os.path.join(d, ".lane-lead")))["role"], "glm")
        self.assertEqual(json.load(open(os.path.join(wt, ".lane-lead")))["holder"], "glm-commander")

    def test_lane_prompt_uses_fleet_dir(self):
        self.a = make_args(fleet_dir="docs/other/fleet")
        self.fleet()
        self.trip_claude()
        self.go()
        p = self.h.prompts("glm-bundle")[0]
        self.assertIn("docs/other/fleet/FLEET.md", p)
        self.assertIn("docs/other/fleet/briefs/bundle.md", p)
        self.assertIn("docs/other/fleet/status/bundle.md", p)
        self.assertNotIn("phase3", p)

    def test_commander_missing_logs_skip_and_lanes_continue(self):
        self.h.agent_list = [ag("fw-bundle", "working", "/wt/bundle", "w1:p2")]
        self.trip_claude()
        self.go()
        self.assertIn("handoff-skip", self.kinds())
        self.assertEqual([c[2] for c in self.h.find("agent", "start")], ["glm-bundle"])

    def test_working_commander_waits(self):
        self.fleet(commander="working")
        self.trip_claude()
        self.step()
        self.settle()
        self.h.agent_list[0]["agent_status"] = "working"
        self.step()
        self.assertIn("handoff-wait", self.kinds())
        self.assertNotIn("glm-commander", [c[2] for c in self.h.find("agent", "start")])


class HandbackTests(Base):
    def setUp(self):
        super().setUp()
        self.fleet()
        self.trip_claude()
        self.go()   # handed off
        self.h.calls.clear()
        snap = json.load(open(fg.STATE))
        self.lane_pane = snap["handoff"]["fw-bundle"]["pane"]
        self.cmd_pane = snap["commander"]["pane"]

    def reset_window(self):
        self.t += 4000
        self.windows = {}

    def test_reset_hands_back_lanes_then_commander_with_single_resume(self):
        self.h.agent_list += [ag("glm-commander"), ag("glm-bundle"), ag("glm-extra", "working")]
        self.reset_window()
        self.step()
        closes = [c[2] for c in self.h.find("pane", "close")]
        self.assertEqual(closes, [self.lane_pane, self.cmd_pane])
        exits = [c[2] for c in self.h.find("agent", "prompt") if c[3] == "/exit"]
        self.assertEqual(exits, ["glm-bundle", "glm-commander"])
        # lane resumes get their own message; commander gets exactly ONE combined message
        self.assertEqual(len(self.h.prompts("fw-commander")), 1)
        cm = self.h.prompts("fw-commander")[0]
        self.assertIn("GLM commander log", cm)
        self.assertIn("glm-bundle", cm)
        self.assertIn("commit(s) on the integration branch", cm)
        self.assertIn("glm-extra", cm)           # unregistered glm agent listed
        self.assertNotIn("glm-bundle,", cm.split("NOT started")[-1])
        self.assertEqual(len(self.h.prompts("fw-bundle")), 1)
        self.assertIn("GLM-5.3 agent (glm-bundle)", self.h.prompts("fw-bundle")[0])
        self.assertFalse(os.path.exists(fg.FLAG))

    def test_unregistered_glm_agents_survive(self):
        self.h.agent_list += [ag("glm-commander"), ag("glm-bundle"), ag("glm-extra", "working")]
        panes = {self.lane_pane, self.cmd_pane}
        self.reset_window()
        self.step()
        closed = {c[2] for c in self.h.find("pane", "close")}
        self.assertEqual(closed, panes)
        self.assertFalse([c for c in self.h.calls if len(c) > 2 and c[2] == "glm-extra" and c[0] == "agent" and c[1] in ("prompt", "send-keys")])

    def test_handback_skipped_prompt_when_zai_paused(self):
        self.st.update(zai_paused=True, zai_wake_at=self.t + 10**6)
        self.reset_window()
        self.step()
        self.assertFalse([c for c in self.h.find("agent", "prompt") if str(c[3]).startswith("HANDBACK")])


class IdleCommanderTests(Base):
    def test_idle_commander_gets_single_combined_resume(self):
        # commander idle at the trip (never in the Esc'd set); a lane is working
        self.h.agent_list = [ag("fw-commander", "idle", CMD_CWD, "w1:p8"),
                             ag("fw-bundle", "working", "/wt/bundle", "w1:p2")]
        self.trip_claude()
        self.go()
        self.assertEqual(self.st["commander"]["agent"], "glm-commander")
        self.h.calls.clear()
        self.t += 4000
        self.windows = {}
        self.step()
        msgs = self.h.prompts("fw-commander")
        self.assertEqual(len(msgs), 1)
        self.assertIn("GLM commander log", msgs[0])
        self.assertIn("glm-commander commanded the fleet", msgs[0])

    def test_paused_but_not_handed_off_gets_plain_resume(self):
        self.h.agent_list = [ag("fw-commander", "working", CMD_CWD, "w1:p8")]
        self.zai = {"error": "down"}      # handoffs disabled while Z.AI status is unknown
        self.trip_claude()
        self.step(); self.step()
        self.assertFalse(self.h.find("agent", "start"))
        self.h.calls.clear()
        self.t += 4000
        self.windows = {}
        self.step()
        msgs = self.h.prompts("fw-commander")
        self.assertEqual(len(msgs), 1)
        self.assertIn("not handed off", msgs[0])
        self.assertNotIn("GLM commander log", msgs[0])


def item(iid, kind="lane", status="ready", **kw):
    d = {"id": iid, "title": f"title {iid}", "kind": kind, "status": status, "providers": ["claude", "glm"],
         "glm-executable": True, "auto-start": True}
    if kind == "lane":
        d["brief"] = f"briefs/{iid.lower()}.md"
    d.update(kw)
    return d


class LedgerTests(Base):
    FD = "docs/led"

    def setUp(self):
        super().setUp()
        self.cmd = os.path.join(self.tmp, "worktrees", "integ")
        os.makedirs(os.path.join(self.cmd, self.FD, "briefs"))
        self.a = make_args(commander_cwd=self.cmd, fleet_dir=self.FD)
        self.git_calls = []
        self._rg = fg.run_git
        fg.run_git = lambda cwd, *a: (self.git_calls.append(a) or (0, "p5-int"))
        self.h.agent_list = [ag("fw-commander", "working", self.cmd, "w1:p8")]

    def tearDown(self):
        fg.run_git = self._rg
        super().tearDown()

    def ledger(self, items, briefs=True):
        for i in items:
            if briefs and i.get("brief"):
                with open(os.path.join(self.cmd, self.FD, i["brief"]), "w") as f:
                    f.write("# brief")
        self.ledger_path = os.path.join(self.cmd, self.FD, "LEDGER.yaml")
        with open(self.ledger_path, "w") as f:
            yaml.safe_dump({"version": 1, "items": items, "windows": []}, f)

    def window(self):
        self.trip_claude()
        self.step()
        self.settle()
        self.step()

    def started(self):
        return [c[2] for c in self.h.find("agent", "start")]

    def cmd_prompt(self):
        return self.h.prompts("glm-commander")[0]

    def test_decision_claude_only_and_noauto_never_started_or_offered(self):
        self.ledger([
            item("W-1"),
            item("W-2", **{"auto-start": False}),
            item("W-3", kind="decision", **{"decision-rights": "user"}),
            item("W-4", kind="commander-task", providers=["claude"], **{"glm-executable": False}),
            item("W-5", kind="evidence-prep"),
            item("W-6", kind="review", **{"auto-start": False}),
            item("W-7", kind="decision", providers=["claude", "glm"]),   # even if marked executable
            item("W-8", kind="commander-task", providers=["claude"]),     # glm-executable true but claude-only
        ])
        self.window()
        self.assertEqual(self.started(), ["glm-commander", "glm-w-1"])
        p = self.cmd_prompt()
        self.assertIn("W-5", p); self.assertIn("W-6", p)
        for bad in ("W-1 ", "W-2", "W-3", "W-4", "W-7", "W-8"):
            self.assertNotIn(bad, p.split("LEDGER")[-1])
        tab = self.h.find("tab", "create")[0]
        self.assertEqual(tab[tab.index("--label") + 1], "glm-w-1")
        self.assertIn(os.path.join(os.path.dirname(self.cmd), "lane-w-1"), tab)

    def test_depends_not_done_is_not_ready(self):
        self.ledger([item("W-1", status="queued"), item("W-2", depends=["W-1"]), item("W-3", depends=["W-99"]),
                     item("W-4", kind="review", depends=["W-1"], **{"auto-start": False})])
        self.window()
        self.assertEqual(self.started(), ["glm-commander"])
        self.assertNotIn("W-4", self.cmd_prompt())

    def test_depends_done_is_ready(self):
        self.ledger([item("W-1", status="done"), item("W-2", depends=["W-1"])])
        self.window()
        self.assertEqual(self.started(), ["glm-commander", "glm-w-2"])

    def test_owner_or_missing_brief_not_started(self):
        self.ledger([item("W-1", owner="fw-x"), item("W-2")], briefs=True)
        os.remove(os.path.join(self.cmd, self.FD, "briefs", "w-2.md"))
        self.window()
        self.assertEqual(self.started(), ["glm-commander"])

    def test_cap_two_per_window(self):
        self.ledger([item("W-1"), item("W-2"), item("W-3")])
        self.window()
        self.assertEqual(self.started(), ["glm-commander", "glm-w-1", "glm-w-2"])
        self.assertIn("autostart-skip", self.kinds())
        self.step(); self.step()                       # later iterations never start more
        self.assertEqual(len(self.started()), 3)
        ev = [e for e in self.events() if e["event"] == "AUTOSTART"]
        self.assertEqual([e["item"] for e in ev], ["W-1", "W-2"])
        self.assertTrue(any(c[:3] == ("worktree", "add", "-b") and c[3] == "lane/w-1" for c in self.git_calls))

    def test_unreadable_ledger_is_v3_behaviour(self):
        for bad in (None, "items: [unclosed", "just a string"):
            with self.subTest(bad=bad):
                self.setUp_again()
                if bad is not None:
                    with open(os.path.join(self.cmd, self.FD, "LEDGER.yaml"), "w") as f:
                        f.write(bad)
                self.window()
                self.assertEqual(self.started(), ["glm-commander"])
                self.assertNotIn("LEDGER", self.cmd_prompt())
                self.assertFalse(self.h.find("tab", "create"))
                self.assertEqual([e for e in self.events() if e["event"] == "ledger"][0]["status"], "unreadable")

    def setUp_again(self):
        self.tearDown(); self.setUp()

    def test_resume_lists_claude_items_delta_and_never_writes_ledger(self):
        self.ledger([item("W-1"), item("W-5", kind="evidence-prep"),
                     item("W-9", kind="decision", providers=["claude"], **{"glm-executable": False, "decision-rights": "user"}),
                     item("W-10", kind="commander-task", providers=["claude"], **{"glm-executable": False, "auto-start": False}),
                     item("W-11", kind="commander-task", providers=["claude"], status="queued",
                          **{"glm-executable": False})])
        before = open(self.ledger_path).read()
        self.window()
        self.assertEqual(open(self.ledger_path).read(), before)
        # during the window the GLM commander finishes W-5 and queues W-12; W-11 becomes ready
        d = yaml.safe_load(before)
        for i in d["items"]:
            if i["id"] == "W-5":
                i.update(status="done", owner="glm-commander")
            if i["id"] == "W-11":
                i["status"] = "ready"
        d["items"].append(item("W-12", kind="commander-task", status="queued"))
        with open(self.ledger_path, "w") as f:
            yaml.safe_dump(d, f)
        self.h.agent_list += [ag("glm-commander"), ag("glm-w-1", "working"), ag("glm-stray")]
        self.h.calls.clear()
        self.t += 4000; self.windows = {}
        self.step()
        msgs = self.h.prompts("fw-commander")
        self.assertEqual(len(msgs), 1)
        m = msgs[0]
        self.assertIn("W-9 [decision, decision-rights user]", m)
        self.assertIn("W-10", m); self.assertIn("W-11", m)
        self.assertNotIn("W-1 [lane", m)                        # glm-capable items are not 'for you'
        self.assertIn("W-5 ready→done owner -→glm-commander", m)
        self.assertIn("W-12 new (queued)", m)
        self.assertIn("glm-w-1 (W-1)", m)                       # auto-started lane listed...
        self.assertNotIn("glm-w-1", m.split("NOT started by the guard")[-1].split("Ledger")[0])  # ...not a stray
        self.assertIn("glm-stray", m)
        self.assertFalse([c for c in self.h.find("pane", "close") if c[2].startswith("w1:pT")])  # not closed


class ContextTests(Base):
    def test_checkpoint_fires_once_and_rearms(self):
        self.h.agent_list = [ag("fw-bundle", "working", session="S1")]
        self.contexts = {"S1": 85}
        self.step()
        self.assertEqual(len(self.h.prompts("fw-bundle")), 1)
        self.assertIn("CONTEXT CHECKPOINT (fleet guard): your context window is at 85%", self.h.prompts("fw-bundle")[0])
        self.assertIn("CTX", self.kinds())
        self.step(); self.contexts["S1"] = 90; self.step()
        self.assertEqual(len(self.h.prompts("fw-bundle")), 1)       # still armed off
        self.contexts["S1"] = 60                                    # not yet below 50
        self.step()
        self.contexts["S1"] = 85; self.step()
        self.assertEqual(len(self.h.prompts("fw-bundle")), 1)
        self.contexts["S1"] = 40                                    # compaction
        self.step()
        self.contexts["S1"] = 82; self.step()
        self.assertEqual(len(self.h.prompts("fw-bundle")), 2)
        self.assertEqual(fg.load_state()["ctx_sent"], {"fw-bundle": 82})

    def test_glm_agents_and_missing_snapshot(self):
        self.h.agent_list = [ag("glm-x", session="S2"), ag("fw-y", session="NOSNAP")]
        self.contexts = {"S2": 99}
        self.step()
        self.assertEqual(len(self.h.prompts("glm-x")), 1)
        self.assertEqual(self.h.prompts("fw-y"), [])

    def test_no_checkpoint_to_paused_claude_agent(self):
        self.h.agent_list = [ag("fw-bundle", "idle", session="S1")]
        self.contexts = {"S1": 95}
        with open(fg.FLAG, "w") as f:
            f.write("x")
        self.st = {"wake_at": self.t + 100}
        self.step()
        self.assertEqual(self.h.prompts("fw-bundle"), [])


class ResetAndZaiTests(Base):
    def test_reset_state_archives(self):
        for p in (fg.STATE, fg.FLAG, fg.EVENTS):
            with open(p, "w") as f:
                f.write("stale")
        dest, moved = fg.reset_state()
        self.assertEqual(sorted(moved), ["PAUSED", "events.jsonl", "state.json"])
        self.assertTrue(os.path.isdir(dest))
        self.assertRegex(os.path.basename(dest), r"^\d{4}-\d\d-\d\d-\d{6}$")
        with open(os.path.join(dest, "state.json")) as f:
            self.assertEqual(f.read(), "stale")
        for p in (fg.STATE, fg.FLAG, fg.EVENTS):
            self.assertFalse(os.path.exists(p))

    def test_zai_trip_pauses_glm_and_resumes(self):
        self.h.agent_list = [ag("glm-a", "working"), ag("glm-b", "idle"), ag("fw-c", "working")]
        self.zai = {"zai_5h": (95, self.t + 600)}
        self.step()
        self.assertEqual(self.h.find("agent", "send-keys"), [("agent", "send-keys", "glm-a", "esc")])
        self.assertTrue(self.st["zai_paused"])
        self.t += 700
        self.zai = {"zai_5h": (0, self.t + 18000)}
        self.step()
        self.assertEqual(len(self.h.prompts("glm-a")), 1)
        self.assertIn("Z.AI usage window reset", self.h.prompts("glm-a")[0])
        self.assertFalse(self.st["zai_paused"])

    def test_claude_trip_pauses_only_working_ri_agents(self):
        self.h.agent_list = [ag("fw-a", "working"), ag("fw-b", "idle"), ag("glm-c", "working")]
        self.trip_claude()
        self.step()
        self.assertEqual(self.h.find("agent", "send-keys"), [("agent", "send-keys", "fw-a", "esc")])
        self.assertTrue(os.path.exists(fg.FLAG))


if __name__ == "__main__":
    unittest.main()
