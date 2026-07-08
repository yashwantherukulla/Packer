# Changelog

Reverse-chronological log of implementation commits. One entry per commit: what
changed / was added, and how it was verified. Newest at the top.

---

## Phase 0 — Foundations

### `chore: convert uv starter to src/packer layout + toolchain config`
- **Task 1.** Turned the bare `uv init` starter into a real `src/` project.
- Added packages: `src/packer/__init__.py`, `src/packer/engine/__init__.py`, `src/packer/engine/common/__init__.py`.
- Removed the `main.py` starter.
- Expanded `pyproject.toml`: runtime deps (numpy, scipy, safetensors, huggingface-hub, hydra-core, omegaconf, pydantic); `dev` group (ruff, mypy, pytest, pytest-cov, hypothesis, import-linter, pre-commit); hatchling build targeting `src/packer`; ruff (py310, curated lint set), mypy (strict), and pytest config (markers, `testpaths`).
- Added `tests/unit/test_smoke.py` (package-import smoke test) and `tests/conftest.py`.
- **Verified:** `uv sync` OK; `uv run pytest tests/unit/test_smoke.py` → 1 passed; `uv run ruff check .` → clean; `uv run mypy src` → no issues.

### `docs: add implementation progress log + branching strategy`
- **Branch:** `phase-0-foundations`
- Added `docs/implementation/` — the living implementation record:
  - `README.md` — folder purpose + branching/commit strategy (per-phase branches, one commit per plan task, `--no-ff` merge to `main`, quality gate on every commit).
  - `STATUS.md` — progress board for all 7 phases and the 12 Phase-0 tasks.
  - `CHANGELOG.md` — this file.
- No code yet; establishes the workflow that every subsequent commit follows.
