# Changelog

Reverse-chronological log of implementation commits. One entry per commit: what
changed / was added, and how it was verified. Newest at the top.

---

## Phase 0 — Foundations

### `docs: add implementation progress log + branching strategy`
- **Branch:** `phase-0-foundations`
- Added `docs/implementation/` — the living implementation record:
  - `README.md` — folder purpose + branching/commit strategy (per-phase branches, one commit per plan task, `--no-ff` merge to `main`, quality gate on every commit).
  - `STATUS.md` — progress board for all 7 phases and the 12 Phase-0 tasks.
  - `CHANGELOG.md` — this file.
- No code yet; establishes the workflow that every subsequent commit follows.
