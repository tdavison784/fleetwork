# Commander state: {{ledger}}

The commander's live state; a successor commander (another provider during a usage window, or a fresh session
after a context reset) resumes from this file, the ledger view (`LEDGER.yaml`), the runtime's agent list and
each running lane's status file, in that order. Update it after every state change and save it.

## Now

<One paragraph: what is running, what is waiting on whom.>

## Lanes

| Item | Lane | Agent | Profile | Workspace | State | Since |
|---|---|---|---|---|---|---|

## Integration log

| When | Item | Lane | Reference (commit / PR / path) | Checks | Cleanup done |
|---|---|---|---|---|---|

## Decisions (with the owner's words where delegated)

<Date — decision — why — ledger item.>

## Open questions for the owner

<Each one is also a `decision` item or a `human` gate in the ledger.>

## Incidents

<Brief deviations and near misses; each one gets an `incident` item and, if it changes a rule, the rule.>

## Next actions

<Ordered; a successor executes these without re-deriving anything. Ready work comes from `ledger ready`.>
