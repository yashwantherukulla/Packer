# Phase 6 — Integration & Release

> **Goal:** prove the whole system works together and make it runnable by others.
> **Depends on:** all phases. **Blocks:** nothing (terminal).
> **Part mapping:** integration + hardening + release across Parts 1–4.

---

## 1. Scope

**In scope**
- **Full E2E chain** as an automated test (the proof the platform works).
- Sandbox **security hardening pass** + a written threat model.
- **Performance pass**: training/detection timings, queue behavior under concurrent load, WS fan-out.
- **`docker-compose`** for the full stack (postgres, redis, api, workers, frontend, sandbox image).
- Operator/run docs + release checklist.
- **Nightly E2E CI** job.

**Out of scope**
- New engine features. Multi-tenant auth, billing, autoscaling (non-goals).

---

## 2. The E2E chain (the acceptance proof)

Automated test (API + Playwright), mirroring ARCHITECTURE §4:

```
1. Pack:    upload a known toy repo (containing one planted benign file and one
            planted malicious file) → job completes → .pak artifact produced.
2. Detect:  run Detect on the artifact → verdict MEMORIZED-CODE-LIKELY with evidence.
3. Extract: exact extraction → reconstructed repo is BYTE-IDENTICAL to the original.
4. Scan:    the planted malicious file scores `malicious`; the benign file `benign`.
5. UI:      all four steps are driven/observed through the browser (Playwright),
            progress streams live, reports render.
```

Passing this end-to-end is the project's definition of done.

---

## 3. Security hardening pass (sandbox threat model)

- Document the threat model: attacker = author of a malicious model / extracted code; boundary = the Docker sandbox; assets = host FS, host network, other jobs.
- Verify each control from ADR-008 with an adversarial test: no-net enforced, read-only root, tmpfs-only writes, `cap-drop=ALL`, `no-new-privileges`, non-root UID, mem/cpu/pids/time limits. Attempt (and fail) to: reach the network, write outside tmpfs, spawn beyond `pids-limit`, exhaust memory, run forever, read host paths.
- Confirm the API/worker **never** execute extracted code outside the sandbox (grep-level + test-level assertion).
- Confirm safetensors-only default holds across all upload paths.

---

## 4. Performance & load pass

- Measure and record: tiny-repo pack time (CPU vs. CUDA), detect time per model size, scan time per file, sandbox startup overhead.
- Concurrency: submit N simultaneous jobs; verify GPU queue serializes `pack` while `detect`/`scan` proceed on the default queue; WS fan-out holds for multiple subscribers.
- Establish baseline numbers in the docs so regressions are visible.

---

## 5. Release & deploy

- `docker/compose.dev.yml` (dev) and a `compose.yml` (full stack) that brings up everything from a clean checkout: `docker compose up --build`.
- Service Dockerfiles (api, worker) + the sandbox image build.
- Alembic migrations run on startup (or a documented `migrate` step).
- Operator docs: how to run, configure (Hydra overrides + env), back up the object store, and read logs (correlation ids).
- Release checklist: all milestone gates green, E2E nightly green, threat-model tests green, docs updated (final documentation sync pass).

---

## 6. Testing plan

- **E2E gate** (§2) runs on a nightly schedule and pre-release, not every PR.
- **Security tests** (§3) run in CI `integration` (they need Docker) and are a hard gate.
- **Load test** is scripted and run manually / nightly; results recorded.
- **Clean-checkout test:** on a fresh clone, `docker compose up --build` yields a working stack (smoke-checked by hitting `/docs` and the frontend).

---

## 7. Development steps (ordered)

1. Author the toy repo fixture with planted benign + malicious files.
2. API-level E2E test (pack→detect→extract→scan) using tiny fixtures.
3. Playwright E2E over the same chain through the UI.
4. Adversarial sandbox tests; close any gaps found.
5. `compose.yml` full stack + service Dockerfiles; clean-checkout smoke.
6. Performance scripts + recorded baselines.
7. Operator docs + release checklist; final docs sync.
8. Wire nightly E2E CI.

---

## 8. Acceptance criteria (milestone gate)

- [ ] The full E2E chain (§2) passes automatically end-to-end, including byte-exact extraction and correct malicious/benign scoring — driven through the UI.
- [ ] All adversarial sandbox containment tests pass; the threat model is documented.
- [ ] `docker compose up --build` brings the full stack online from a clean checkout.
- [ ] Performance baselines are recorded.
- [ ] Nightly E2E CI job is green; all prior phase gates remain green.

---

## 9. Risks

- **Flaky E2E** (timing, WS) → generous timeouts, deterministic fixtures, retries only on infra flake (not on assertion failures).
- **Compose parity with dev** → single source of truth for service config via Hydra + env; avoid drift between `compose.dev.yml` and `compose.yml`.
- **Sandbox gaps found late** → security sub-track started in Phase 3, so hardening here is verification, not first discovery.
