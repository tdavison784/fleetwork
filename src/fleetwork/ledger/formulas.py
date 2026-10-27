"""Formulas (LEDGER-DESIGN §4.4): YAML templates that expand into linked items. The kit's `lane` formula is
packs/core/formulas/lane.yaml; projects add their own under <ledger>/formulas/."""
from fleetwork.errors import NotImplementedYet


def expand(formula_dict, variables, next_id):
    """Items (as dicts) with edges in place; `next_id()` hands out sequential ids."""
    raise NotImplementedYet("formulas.expand", "WP-07", "LEDGER-DESIGN §4.4")
