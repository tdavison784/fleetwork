"""Lane lifecycle (ROADMAP 'The kit'; LEDGER-DESIGN §7): start, watch, merge, cleanup.

  start   ledger claim -> workspace.create -> enforcement.write -> runtime.start(profile, brief)
  watch   wait until the workspace's tip moved AND the runtime reports idle/done; never match screen text
  merge   one re-runnable transaction: done signal + status file present, diff inside ownership and off
          guard.freeze, project checks pass, integration.integrate, runtime.stop, workspace.remove,
          ledger close. Any failure leaves the item in-progress with a note.
"""
from fleetwork.errors import NotImplementedYet


def start(project, ledger_dir, item_id, actor):
    raise NotImplementedYet("fleet lane start", "WP-09", "LEDGER-DESIGN §7")


def watch(project, ledger_dir, item_id, timeout=None):
    raise NotImplementedYet("fleet lane watch", "WP-09", "LEDGER-DESIGN §7")


def merge(project, ledger_dir, item_id, actor):
    raise NotImplementedYet("fleet lane merge", "WP-10", "LEDGER-DESIGN §7")
