PY ?= python3
export PYTHONPATH := src

.PHONY: test check

# Every test in the repository: the kit (tests/), the guard and the beads mirror.
test:
	$(PY) -m pytest -q

# What a work package must pass before it reports done (AGENTS.md "Workflow").
check: test
	$(PY) -m fleetwork.ledger.cli --help >/dev/null
	$(PY) -m fleetwork.runtime.cli --help >/dev/null
	$(PY) -m fleetwork.runtime.cli packs >/dev/null
