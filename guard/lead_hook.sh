#!/usr/bin/env bash
# PreToolUse hook: lane-lead signal. In a git worktree that has a .lane-lead file,
# only the lead role may modify files. Role of this session: $FLEET_ROLE if set,
# else "glm" when talking to the Z.AI endpoint, else "claude".
# No .lane-lead file → no-op (exit 0), so this never affects other projects.
input="$(cat)"
cwd="$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"
top="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)" || exit 0
lead_file="$top/.lane-lead"
[ -f "$lead_file" ] || exit 0

lead="$(jq -r '.role // empty' "$lead_file" 2>/dev/null)"
[ -z "$lead" ] && exit 0
role="${FLEET_ROLE:-}"
if [ -z "$role" ]; then
    case "${ANTHROPIC_BASE_URL:-}" in *z.ai*) role="glm" ;; *) role="claude" ;; esac
fi
[ "$role" = "$lead" ] && exit 0

tool="$(printf '%s' "$input" | jq -r '.tool_name // empty')"
block=0
case "$tool" in
    Edit|Write|MultiEdit|NotebookEdit) block=1 ;;
    Bash)
        cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"
        if printf '%s' "$cmd" | grep -Eq '(^|[;&|(]|\s)(git\s+(add|commit|merge|rebase|reset|checkout|switch|restore|stash|cherry-pick|revert|rm|mv|apply|am|tag|branch\s+-[dDmM])|rm|mv|cp|touch|mkdir|tee|gofmt\s+-w|goimports\s+-w|sed\s+-i|perl\s+-i|truncate|ln)(\s|$)|[^0-9<]>{1,2}\s*[^&|]'; then
            block=1
        fi
        ;;
esac
[ "$block" -eq 0 ] && exit 0

holder="$(jq -r '.holder // "?"' "$lead_file" 2>/dev/null)"
echo "LANE LEAD: this worktree's lead is '$holder' (role $lead); you are role '$role', so you must not modify files here right now. Stop working on this lane and wait — the fleet guard will hand the lead back to you." >&2
exit 2
