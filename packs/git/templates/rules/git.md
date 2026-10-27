# Rules: git (pack)

- Each lane works on its own branch in its own worktree, cut from the integration branch. Commit early and
  often on your branch. Never push, never merge into other branches, never rebase other lanes' branches. If
  you need newer integration work, the commander tells you to merge the integration branch into yours.
- Only the commander merges into the integration branch, with the project's merge policy
  (`{{merge_policy}}` unless `.fleet.toml` `[git] merge` says otherwise).
- Commit messages: imperative summary line, a body that explains why, and the attribution line your
  harness requires. An agent continuing a lane on a fallback provider prefixes every subject with the tag
  its profile's `fallback` names, so its commits stay reviewable.
- Never `git stash` without a unique message and applying by SHA: the stash is shared by every worktree.
  Prefer a temporary WIP commit.
- Branch deletes: `git branch -d` only. A refused delete means unmerged work; report it.
- The diff of your branch must stay inside what your brief owns and off every frozen path; `fleet lane merge`
  checks this and refuses otherwise.
