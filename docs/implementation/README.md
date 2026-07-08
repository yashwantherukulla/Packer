# Implementation Log

This folder is the **living record of how Packer gets built**. Unlike the specs and
plans (which describe intent), these files describe *what has actually happened* and
*where we are right now*. They are updated in the **same commit** as the change they
describe — every commit touches this folder.

| File | Purpose |
|------|---------|
| [`STATUS.md`](STATUS.md) | The progress board: every phase and task with a checkbox and current state. Read this first to see where the project stands. |
| [`CHANGELOG.md`](CHANGELOG.md) | Reverse-chronological log — one entry per commit: what changed, what was added, and how it was verified. |
| `README.md` | This file: what the folder is and the workflow that keeps it accurate. |

## Branching & commit strategy

- **`main`** is the stable integration branch. It always stays green (CI passes, `main` is releasable).
- **Per-phase feature branches.** Each [ROADMAP](../ROADMAP.md) phase is built on its own
  short-lived branch: `phase-0-foundations`, `phase-1-packer`, `phase-2-detector`, … cut from an up-to-date `main`.
- **One commit per plan task.** Each task in the corresponding [plan](../plans/) becomes exactly one
  [Conventional Commit](https://www.conventionalcommits.org/) (`feat(...)`, `chore:`, `ci:`, `docs:`) —
  one logical change, tests included.
- **Merge at phase end.** When a phase's Definition of Done is met and CI is green, the branch is merged
  into `main` with `git merge --no-ff` so the merge commit marks the phase boundary; the feature branch is then deleted.
- **Quality gate on every commit.** `pre-commit` runs ruff (lint + format), mypy (strict), and import-linter
  before the commit is accepted. See [DEVELOPMENT.md](../DEVELOPMENT.md) §3.
- **Every commit updates this folder** — the `CHANGELOG.md` entry and the `STATUS.md` checkbox land in the
  same commit as the code they describe.
