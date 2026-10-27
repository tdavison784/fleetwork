# Rules: eval-integrity (pack)

- `PROTOCOL.md` is fixed before the first scored run. Thresholds, arms and reading rules are never edited
  after it; amendments are appended, dated, with why. A failing result is a finding to report, not a number
  to move.
- Ground truth (`{{sealed_glob}}`) is written only by the ground-truth lane, from primary sources, with
  citations, and is never derived from the output of what is being measured. Every other lane's item lists
  it under `guard.forbid-read`; the hooks deny it, and its branch is not merged before scoring is done.
- Runs of the thing under test see only their prepared inputs. The canary proves the isolation before the
  first scored run and again after any change to the harness.
- Scores quote the run's own text, and every quote is checked mechanically against that text.
- Report provenance honestly: deterministic (a validator proved it), observed (a real outcome), human,
  proxy (an AI acting as reviewer, always labelled).
