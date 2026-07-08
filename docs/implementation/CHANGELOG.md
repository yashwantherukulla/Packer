# Changelog

Reverse-chronological log of implementation commits. One entry per commit: what
changed / was added, and how it was verified. Newest at the top.

---

## Phase 0 — Foundations

### `ci: add quality + integration workflow via setup-uv`
- **Task 3.** Added `.github/workflows/ci.yml` with two jobs, both on `astral-sh/setup-uv` (cached) + `uv sync`:
  - `quality`: ruff check → ruff format --check → mypy src → lint-imports → unit tests (with coverage).
  - `integration`: `pytest tests/integration -m integration`.
- The `lint-imports` step gains its config in Task 9; `tests/integration` is populated in later phases. No git remote yet, so CI is not exercised — the workflow is valid YAML and ready for when a remote is added.
- **Verified:** `check-yaml` pre-commit hook passes on the workflow file.

### `chore: add pre-commit with ruff lint+format and mypy`
- **Task 2.** Added `.pre-commit-config.yaml`: ruff (`--fix`), ruff-format, mypy (strict, `src/`, with pydantic dep), plus hygiene hooks (end-of-file-fixer, trailing-whitespace, check-yaml, check-added-large-files ≤1 MB, check-merge-conflict, detect-private-key).
- Installed the hook (`pre-commit install`) so lint/format/type-checks run on every commit from here on.
- **Exempted** `docs/plans/2026-07-07-phase-3-extractor-sandbox.md` from `detect-private-key`: that plan documents the secrets scanner (a truncated, non-real key header fixture + the scanner's own detection regex), which the hook flags as a false positive. Kept the canonical config in `DEVELOPMENT.md` §3.2 in sync.
- **Verified:** `uv run pre-commit run --all-files` → all hooks Passed (exit 0).

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
