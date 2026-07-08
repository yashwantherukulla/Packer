# Changelog

Reverse-chronological log of implementation commits. One entry per commit: what
changed / was added, and how it was verified. Newest at the top.

---

## Phase 6 — Integration & Release

### `test(e2e): drive the pack->detect->extract+scan chain through the UI (Playwright)`
- **Task 4.** Added `frontend/e2e/chain.spec.ts` — the §6.4 chain THROUGH the browser: uploads the toy zip on `/pack` (Uploader auto-submits), asserts live `job-progress` then the `pack-result` card with honest `Original`/`Artifact (.pak)` sizes, parses the produced artifact id from the `.pak` `download` href, then drives `/detect` (`model-ref=artifact:<id>` → `verdict-badge` reads `MEMORIZED-CODE-LIKELY`, `limitations` shows the /signature/ note) and `/scan` (`model-ref=artifact:<id>` chains extract→scan → `reconstruction` shows byte-exact, `report-scan` + `findings-table` row for `exfil.py` reads malicious/high). Extended `frontend/playwright.config.ts` (existing Phase-5 minimal config) to Phase-6 needs: 15-min test timeout (pack training dominates), CI retries, `video: retain-on-failure`, a `chromium` project, and a `PACKER_E2E_FRONTEND_URL` baseURL aligned with the Python harness (keeps `E2E_BASE_URL` fallback for the Phase-5 happy-path specs).
- Reconcile: `frontend/package.json` already carries `"e2e": "playwright test"` + `@playwright/test` (added in Phase 5) — no change needed. The three Phase-5 happy-path specs and the shared config are extended, not duplicated.
- Deviations + why:
  - **Real testids, not the plan's `artifact-card`/`risk-badge`.** Phase 5 shipped the testid vocabulary `pack-result` / `verdict-badge` / `findings-table` / `report-scan` / `reconstruction` / `limitations` / `download`. The scan report's risk verdict renders through the shared `verdict-badge` (VerdictBadge branches on `kind`), so there is no separate `risk-badge`. Wrote the spec against the existing hooks — **zero Phase-5 component changes** (cleaner than adding parallel testids).
  - **Chain via parsed artifact id, not a "use latest artifact" button.** The UI has no such affordance (would be a redesign); instead the spec parses the artifact id from the pack-result download href and feeds `artifact:<id>` into detect/scan — a genuine chain through the real UI.
  - **ESM-safe `__dirname`.** `package.json` is `"type": "module"`; the plan's top-level `__dirname` throws under ESM at list time. Used `path.dirname(fileURLToPath(import.meta.url))`.
  - **Live run deferred to CI (Docker down / no running stack).** Same posture as the Phase-5 happy-path specs.
- **Verified:** from `frontend/` — `npx playwright test --list` → **4 tests in 4 files** (chain.spec.ts discovered alongside the 3 happy-path specs; config + specs parse). `npm run typecheck` → clean. `npm run lint` → 0 errors. Live Playwright run against the stack deferred to the Task-12 nightly E2E job (Docker down).

### `test(e2e): assert the §6.4 pack->detect->extract->scan chain via the API`
- **Task 3.** Added `tests/e2e/test_chain_api.py` — the single §6.4 acceptance-proof test (httpx, `e2e`-marked): packs the toy repo via `POST /pack` (tiny `e2e_tiny` overrides), asserts `manifest.metrics.lossless`, detects `MEMORIZED-CODE-LIKELY` with a >0 confidence and the ADR-007 "signature, not proof" limitation, exact-extracts, then **cross-checks byte-exactness directly against the real `.pak`** via `ExactExtractor` (delegates to the Phase-1 `unpack_bundle`, one decode path) — `extraction.files == read_repo()` byte-identical — and finally scans the reconstructed units to the expected `benign`/`malicious` per-file verdicts.
- Deviations + why:
  - **`ExactExtractor.extract` takes an `ExtractTarget`, not a bare `Path`.** The plan snippet called `ExactExtractor().extract(host_pak_path(artifact))`; the real Phase-3 signature is `extract(target: ExtractTarget)` (`model_ref: ModelRef`, `pak_path: Path | None`). Wrapped the host-mounted `.pak`: `ExtractTarget(model_ref=ModelRef(kind="pak", value=str(pak)), pak_path=pak)`. No engine change.
  - **Live wiring verification deferred to CI (Docker down).** The plan's Step-2/3 "run → discover wiring gap → fix the seam" loop (e.g. `model_ref="artifact:<id>"` resolution, `/scan {extraction_id}` chaining, artifact host-mount) requires the running stack, which is not available here. The test is authored faithfully and skips cleanly; the nightly E2E job (Task 12) is the hard gate that exercises and, if needed, drives those one-line composition fixes. No speculative, unverifiable API rewiring was added (per "add no new engine logic" / "compose only").
- **Verified:** `uv run pytest tests/e2e -m "not integration and not e2e"` → **3 passed, 3 deselected** (chain + stack_up correctly deselected, no import/collection errors). `uv run pytest tests/e2e/test_chain_api.py -m e2e` → **1 skipped** (no stack). `uv run ruff check --fix tests/e2e` + `ruff format` → clean. Full live chain execution deferred to CI (Docker down).

### `test(e2e): add stack-lifecycle harness, api client, job/pak helpers`
- **Task 2.** Added `tests/e2e/conftest.py`: the session-scoped `compose_stack` fixture (brings the full stack up once via `docker compose -f docker/compose.yml up -d --build`, waits on `/docs`, tears down with `down -v`; **reuses an externally-managed stack** when `PACKER_E2E_BASE_URL` is set — the nightly-CI path; **skips cleanly** when neither the env var nor `docker/compose.yml` (Task 9) is present), the `api_client` httpx `Client` fixture, `wait_for_job(client, job_id, timeout)` (polls `/jobs/{id}` to a terminal state, asserts `succeeded`), and `host_pak_path(artifact_meta)` (maps a container `pak_path` to the host-mounted `outputs/e2e-artifacts/` dir for the byte-exact cross-check). Added `tests/e2e/test_stack_up.py` (`e2e`-marked clean-checkout smoke: `/openapi.json` + `/docs` + frontend root).
- Deviations: none (verbatim; ruff-format collapsed the `_compose` helper to one line).
- **Verified:** `uv run pytest tests/e2e/test_stack_up.py -m e2e -v` → **2 skipped** (compose file absent → `compose_stack` skips, as designed; live run is a Task-12 nightly-CI gate — Docker is down on this host). `uv run ruff check --fix tests/e2e` → All checks passed; `uv run ruff format tests/e2e` → clean. Full stack lifecycle + `test_stack_up` execution deferred to CI (Docker down).

### `test(e2e): add toy-repo fixture (benign+malicious) and tiny pack config`
- **Task 1.** Added the backend E2E fixture `tests/e2e/fixtures/toy_repo/` with exactly two planted units: `hello.py` (benign — static/dynamic passes find nothing high-severity) and `exfil.py` (deliberately malicious: socket beacon to a non-routable address, `subprocess.Popen`, `base64`+`exec`, and a hardcoded AWS-key-like secret — INERT, sandbox-only). Added `expected.py` (single source of truth: `DETECT_VERDICT="MEMORIZED-CODE-LIKELY"`, `FILE_LABELS`, `PACK_OVERRIDES={"engine/pack":"e2e_tiny"}`), the deterministic zip builder `build_toy_repo.py` (`build_toy_repo`/`read_repo`, sorted paths + fixed mtime → reproducible pack input + byte-exact oracle), and `conf/engine/pack/e2e_tiny.yaml` (2-layer/64-dim/40-epoch CPU decoder so `pack` finishes in seconds; losslessness is convergence-invariant per ADR-006). Added the fixture shape gate `tests/e2e/test_toy_repo_fixture.py` (no stack needed).
- Fixture-lint excludes (so hooks never lint/rewrite planted data):
  - `pyproject.toml` `[tool.ruff]` `extend-exclude` → added `"tests/e2e/fixtures"` (alongside `"tests/fixtures"`).
  - `.pre-commit-config.yaml`: added `^tests/e2e/fixtures/` to `end-of-file-fixer` and `trailing-whitespace` excludes (keep the planted files byte-pristine for the byte-exact oracle); added `tests/e2e/fixtures/toy_repo/exfil.py` (and the phase-6 plan) to the `detect-private-key` exclude for the AWS-key-like `API_TOKEN` pattern.
- Deviations + why:
  - **No `tests/e2e/__init__.py` / `tests/e2e/fixtures/__init__.py`.** The repo's test tree is namespace-package based (no `__init__.py` under `tests/`, `tests/unit/`, or `tests/integration/`); cross-imports like `from tests.unit.fakes import …` already work via `pythonpath=["."]` + `--import-mode=importlib`. Following the plan's literal `__init__.py` would split module identity under importlib (dir has `__init__.py`, parent doesn't). Kept the established layout; `from tests.e2e.fixtures.build_toy_repo import …` resolves cleanly (verified by the passing gate).
- **Verified:** `uv run pytest tests/e2e/test_toy_repo_fixture.py -v` → **3 passed** (one-benign-one-malicious invariant, files present, zip byte-deterministic). `uv run ruff check --fix tests/e2e conf` → All checks passed (fixtures correctly excluded); `uv run ruff format tests/e2e` → unchanged; `uv run mypy src` → clean (104 files); `uv run lint-imports` → 3 contracts kept. Full runnable suite `uv run pytest -m "not integration and not e2e"` → **165 passed, 10 deselected**.

## Phase 5 — Web UI

### `test(ui): add Playwright E2E for pack/detect/scan happy paths`
- **Task 14.** Added `frontend/playwright.config.ts` (`testDir: ./e2e`, 180s test / 60s expect timeouts, `baseURL` from `E2E_BASE_URL` default `http://localhost:5173`, no `webServer` — the full stack comes up via docker compose in Phase 6). Added the three happy-path specs `e2e/pack.spec.ts` (upload `toy_repo.zip` → `job-progress` → `pack-result` with Original/Artifact + `download`), `e2e/detect.spec.ts` (`model-ref` → `submit` → `verdict-badge` + `report-detect` + `limitations` /signature/), `e2e/scan.spec.ts` (`model-ref` → `submit` → `reconstruction` + `report-scan` + `findings-table`). Added the tiny fixture `e2e/fixtures/toy_repo.zip` (README.md + main.py + utils.py, 479 B). Added the `"e2e": "playwright test"` npm script.
- Deviations + why:
  - **Vitest `include` scoped to `src/`.** Vitest's default include (`**/*.{test,spec}.*`) swept the Playwright `e2e/*.spec.ts` into the unit run and failed to collect them (Playwright's `test()` cannot run under Vitest). Set `test.include: ["src/**/*.{test,spec}.{ts,tsx}"]` in `vite.config.ts` so `npm run test` (Vitest) owns `src/` only and `npm run e2e` (Playwright runner) owns `e2e/` — the two gates stay fully isolated.
  - **E2E execution deferred to Phase 6.** These specs consume the whole running stack (API + workers + Redis + Postgres + built frontend); they do **not** mock the API. That stack is not runnable on this host (Docker daemon down, no live services) — same posture as the Phase-3/4 testcontainer suites. The specs, config, fixture, and Chromium browser (installed to the ms-playwright cache outside the repo) are all ready; Phase 6 wires them into its E2E job with `E2E_DETECT_REF`/`E2E_SCAN_REF` pointing at Phase-1/3 `.pak` fixtures.
- **Verified:** from `frontend/` — `npx playwright test --list` → 3 tests in 3 files discovered (config + specs parse). `npm run test -- --run` → **20 files / 27 tests passed** (Vitest, e2e correctly excluded). `npm run typecheck` clean; `npm run lint` → 0 errors; `npm run build` → dist bundle built. Live E2E run deferred to Phase 6 (no running stack on this host).

### `feat(ui): add Detect + ExtractScan + Report pages and route wiring`
- **Task 13.** Added `src/pages/Detect.tsx` (model picker → `useSubmitDetect` → progress → detect `ReportView`), `src/pages/ExtractScan.tsx` (model picker → `useSubmitScan` → progress → `byte-exact ✓` / `best-effort` reconstruction banner from the report `evidence.extraction.mode` → scan `ReportView`), and `src/pages/Report.tsx` (renders any stored report by id). Wired `/detect`, `/scan`, `/reports/:id` into `src/router.tsx`. All three routes are composition only.
- Deviations: none beyond the Task 11 `useReport` view-model return (the pages consume `report.data` as the render-ready `ReportBody` exactly as the plan's snippets do).
- **Verified:** from `frontend/` — `npm run test -- --run src/pages/Detect.test.tsx src/pages/ExtractScan.test.tsx` → 2 files / 2 tests passed (Detect posts `{model_ref}` and renders `report-detect`; ExtractScan shows the byte-exact banner and `report-scan`). Full unit suite `npm run test -- --run` → **20 files / 27 tests passed**. `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add Pack + Jobs + JobDetail pages and route wiring`
- **Task 12.** Added `src/pages/Pack.tsx` (drop `.zip` → epochs → `useSubmitPack` → live `JobProgress` → `PackResultCard` on success), `src/pages/Jobs.tsx` (status filter → `useJobs` → rows linking to detail), `src/pages/JobDetail.tsx` (routed detail: `useJob` + `useJobProgress`, then `PackResultCard` for pack jobs / `ReportView` for detect+scan). Wired `/pack`, `/jobs`, `/jobs/:id` into `src/router.tsx`. Pages are composition only — all fetching lives in hooks.
- Deviations + why:
  - **Artifact metrics field is `metrics_json`.** The generated `ArtifactResponse` exposes `metrics_json` (opaque dict), not `metrics` as the plan assumed, so Pack/JobDetail read `artifact.data.metrics_json as unknown as ArtifactMetrics`.
- **Verified:** from `frontend/` — `npm run test -- --run src/pages/Pack.test.tsx src/pages/Jobs.test.tsx` → 2 files / 2 tests passed (uploading a `.zip` calls `mutate` once and streams the `train` step; Jobs lists the row and links to `/jobs/abcdef12`). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add unified ReportView (kind-branch) + honest-metrics PackResultCard`
- **Task 11.** Added `src/components/ReportView.tsx` — the **single** report renderer: shared `VerdictBadge` + a shared `limitations` list, branching on `report.kind` **only** (`detect` → `SignalBreakdown`; `scan` → `FindingsTable` + `BehaviorPanel`). Added `src/components/PackResultCard.tsx` — `<PackResultCard metrics downloadHref />` with honest `Original`/`gzip`/`Artifact (.pak)` sizes, the "not a compressor" ratio-vs-original note, and a `.pak` download link. Updated `src/hooks/useJob.ts` `useReport` to map the wire `ReportResponse` through `toReportBody` and return the flat `ReportBody`.
- Deviations + why:
  - **`ReportView` consumes the `ReportBody` view model, not the wire `Report`.** The wire `ReportResponse` nests the body in an opaque `report` dict (see Task 9), so the plan's `report: Report` prop and `Report["sections"]` access do not typecheck against the real generated type. `ReportView` takes the flat `ReportBody`; `useReport` is the single conversion point (`toReportBody`), keeping all Task 12/13 page composition code verbatim (`report.data` is already render-ready). The plan's `ReportView.test.tsx` fixtures are typed `as unknown as ReportBody` instead of `Report` (same flat data the plan wrote).
  - `useReport`'s return type widened from `Report` (wire) to `ReportBody` (view). Only page code (Tasks 12–13) consumes it; `useJob.test.tsx` (Task 5) tests only `useJob` and is unaffected.
- **Verified:** from `frontend/` — `npm run test -- --run src/components/ReportView.test.tsx src/components/PackResultCard.test.tsx` → 2 files / 3 tests passed (detect → signals + verdict + "signature not proof" limitation, no findings-table; scan → findings + behavior, no signal-breakdown; honest 175.8 KB / 46.9 KB / 6.7 MB sizes + download href). Full suite `npm run test -- --run` → **16 files / 23 tests passed**. `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add FindingsTable (severity sort) + BehaviorPanel (disagreement callout)`
- **Task 10.** Added `src/components/FindingsTable.tsx` — `<FindingsTable findings />`, columns severity/rule/file/line/note; default sort severity-descending (rank critical>high>medium>low), header button (`data-testid="sort-severity"`) toggles direction; severity chip toned by `severityTone`. Added `src/components/BehaviorPanel.tsx` — `<BehaviorPanel behavior />`, syscalls / fs-writes / blocked-net lists plus a `role="alert"` `data-testid="disagreement"` static/dynamic disagreement callout when present.
- Deviations: none — implemented verbatim from the plan (consumes the `Finding`/`Behavior` view models from Task 9).
- **Verified:** from `frontend/` — `npm run test -- --run src/components/FindingsTable.test.tsx src/components/BehaviorPanel.test.tsx` → 2 files / 2 tests passed (default first row `high`, toggles to `low` on header click; behavior lists render `execve` and the disagreement alert). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add VerdictBadge + SignalBreakdown + report section view models`
- **Task 9.** Added `src/lib/report-view.ts` — the sanctioned presentational view models over the opaque wire report body: `Verdict`, `ReportSection`, `ReportBody`, `SignalItem`, `Finding`, `Behavior`, a `toReportBody(res)` flattener, and `sectionsByType(body) → { signals, findings, behavior }`. Added `src/components/VerdictBadge.tsx` — `<VerdictBadge kind label score confidence />` toned by `verdictTone` (detect) / `riskTone` (scan) via `toneClasses`. Added `src/components/SignalBreakdown.tsx` — `<SignalBreakdown signals />`, one card per signal with score, confidence, and its evidence key/values.
- Deviations + why:
  - **Real wire shape drives the view model.** The generated `ReportResponse` (re-exported `Report`) is `{ id, job_id, kind, report: { [k]: unknown } }` — verdict/sections/evidence/limitations are **nested inside the opaque `report` dict**, not top-level as the plan's snippets assumed. So `report-view.ts` adds a `ReportBody` flat view model plus `toReportBody(res)` (promotes `kind`, spreads the opaque body with safe defaults). `sectionsByType` is typed over `ReportBody` (the plan's `Report["sections"][number]` does not exist on the wire type). This is exactly the `dict` carve-out the previous agent flagged as Task 9 work.
- **Verified:** from `frontend/` — `npm run test -- --run src/components/VerdictBadge.test.tsx src/components/SignalBreakdown.test.tsx` → 2 files / 2 tests passed (detect badge shows label + 91% + 80% + red tone; one card per signal with evidence key `alpha` = `2.1`). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add presentational JobProgress bar with fallback indicator`
- **Task 8.** Added `src/components/JobProgress.tsx` — `<JobProgress step pct detail? status? connected />`, a pure presentational live progress bar. Clamps `pct` (0..1) and renders an ARIA `progressbar` with `aria-valuenow` in whole percent (0–100), the step/status line, an optional `detail` line, and — when `connected=false` — a `role="status"` `data-testid="fallback-indicator"` "live stream lost — polling for updates" note (the WS-loss → Query-polling signal from `useJobProgress`).
- Deviations: none — implemented verbatim from the plan.
- **Verified:** from `frontend/` — `npm run test -- --run src/components/JobProgress.test.tsx` → 1 file / 2 tests passed (clamped 40% + detail + no fallback when connected; fallback indicator when disconnected). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add presentational Uploader with extension/size validation`
- **Task 7.** Added `src/components/Uploader.tsx` — `<Uploader accept label maxBytes? onFile />`, a pure presentational, keyboard-focusable native file input with an `aria-label`. Validates the comma-separated `accept` extensions and optional `maxBytes`; on a valid selection it calls `onFile(file)` and shows the name (`role="status"`), on an invalid one it shows a `role="alert"` message and does not fire `onFile`.
- Deviations + why:
  - The reject test now passes `{ applyAccept: false }` to `userEvent.upload`. With the default, user-event's `applyAccept` filters the `.txt` against the input's native `accept=".zip"` before it ever reaches the component, so the component's own extension validation (the behavior under test) never runs. Disabling it exercises the component's `validate()`, which is the point of the test.
- **Verified:** from `frontend/` — `npm run test -- --run src/components/Uploader.test.tsx` → 1 file / 2 tests passed (accepts `.zip` → `onFile` + name; rejects `.txt` → `role="alert"` mentioning `.zip`, no `onFile`). Full suite `npm run test -- --run` → **9 files / 14 tests passed**. `npm run typecheck` clean; `npm run lint` → 0 errors; `npm run build` → dist bundle built.

### `feat(ui): add useJobProgress with WS live stream + Query polling fallback`
- **Task 6.** Added `src/hooks/useJobProgress.ts` — `useJobProgress(jobId) → { event: ProgressView | null, connected, status? }`. Subscribes to `/ws/jobs/{id}` via `createJobProgressSocket` (Task 4); while the socket is open the latest live `ProgressView` wins, and on socket loss (`connected=false`) it derives a `ProgressView` from the polled `useJob` row (`progress_step`/`progress_pct`) so the UI keeps advancing until reconnect (Query is authoritative). `status` comes from the Query job row.
- Deviations: none — implemented verbatim from the plan.
- **Verified:** from `frontend/` — `npm run test -- --run src/hooks/useJobProgress.test.tsx` → 1 file / 1 test passed (live WS event wins; on close it falls back to the polled `{step:"train", pct:0.2, detail:null}` row). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add TanStack Query provider, job/report/artifact + submit hooks`
- **Task 5.** Added `src/hooks/queryClient.ts` (shared `QueryClient`, `staleTime: 1000`, no refetch-on-focus) and wrapped the router in `main.tsx` with `QueryClientProvider`. Added `src/hooks/useJob.ts` — `useJob(id)` (GET `/jobs/{job_id}`, auto-polls 1.5s until terminal `succeeded|failed|cancelled` — the polling source of truth), `useJobs(filters)` (GET `/jobs`), `useReport(id)`/`useArtifact(id)` (GET `/reports/{report_id}` · `/artifacts/{artifact_id}`, disabled on `null`). Added `src/hooks/useSubmit.ts` — `useSubmitPack` (multipart FormData → POST `/pack`), `useSubmitDetect`/`useSubmitScan` (`{model_ref}` → POST `/detect` · `/scan`); each returns the created `Job` and invalidates the `["jobs"]` list.
- Deviations + why:
  - **Real path params:** hooks use `/jobs/{job_id}`, `/reports/{report_id}`, `/artifacts/{artifact_id}` (plan assumed `{id}`).
  - **`useJobs` unwraps `JobList`:** GET `/jobs` returns `{ jobs: [...] }` (the `JobList` wrapper), not a bare array, so `useJobs` returns `data?.jobs ?? []` (the plan's `data as Job[]` assumed an array).
  - **`useSubmitPack` bodySerializer cast:** the generated `/pack` body type is the multipart object `{ file: string }`, not `FormData`, so the passthrough serializer is `(b) => b as unknown as FormData` (plan typed it `(b: FormData) => b`, which fails strict typecheck).
  - **`useSubmit.test.tsx` uses `vi.hoisted`:** `vi.mock` is hoisted above module init, so the POST spy is created via `vi.hoisted` to be referenceable in the factory (the plan's top-level `const POST` → "cannot access before initialization").
- **Verified:** from `frontend/` — `npm run test -- --run src/hooks/useJob.test.tsx src/hooks/useSubmit.test.tsx` → 2 files / 2 tests passed (useJob returns the row; useSubmitDetect posts `model_ref` and yields the job). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add WebSocket job-progress client with reconnect backoff`
- **Task 4.** Added `src/lib/ws.ts` — `createJobProgressSocket(jobId, handlers, opts) → { close }`: opens `ws(s)://<host>/ws/jobs/{id}`, parses each frame as the (hand-authored) `ProgressEvent`, reconnects with exponential backoff (`baseDelay * 2 ** retries`) up to `maxRetries`, and reports `onOpen`/`onClose(willReconnect)` so the hook can flip to polling. Timing + `url()` are injectable for deterministic fake-timer tests; caller `close()` suppresses reconnect.
- Deviations + why:
  - Removed an unused `const sock = MockWS.last!` in the "caller close() suppresses reconnect" test — it was dead and tripped strict `noUnusedLocals`/eslint `no-unused-vars`. The assertion (`MockWS.last` unchanged after `close()` + timer advance) is unchanged.
- **Verified:** from `frontend/` — `npm run test -- --run src/lib/ws.test.ts` → 1 file / 2 tests passed (frame parse + reconnect on unexpected close; caller `close()` suppresses reconnect). `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): add verdict/risk color scale + byte/pct formatters`
- **Task 3.** Added `src/lib/verdict.ts` — the single accessible tone scale: `verdictTone` (detect `MEMORIZED-CODE-LIKELY|INCONCLUSIVE|UNLIKELY` → `danger|warn|ok`), `riskTone` (scan `malicious|suspicious|benign`), `severityTone` (`critical|high|medium|low`), and `toneClasses: Record<Tone, string>` (light + `dark:` Tailwind classes per tone). Added `src/lib/format.ts` — `formatBytes` (unit-scaling), `formatPct` (fraction → rounded %), `formatRatio` (`×`-suffixed). Both are framework-agnostic, no dependencies.
- Deviations: none — implemented verbatim from the plan.
- **Verified:** from `frontend/` — `npm run test -- --run src/lib/verdict.test.ts src/lib/format.test.ts` → 2 files / 5 tests passed. `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): generate typed OpenAPI client + CI drift check`
- **Task 2.** Committed `frontend/openapi.json` — a snapshot of the Phase-4 OpenAPI document generated via `uv run python -c "...create_app().openapi()..."` (route introspection only; no DB/Redis) and normalized to LF. Generated `src/api/schema.d.ts` with `openapi-typescript` (never hand-edited). Added `src/api/client.ts` (`createClient<paths>({ baseUrl: "/api" })`), `src/api/types.ts` (re-exports the generated wire types), and `.github/workflows/frontend.yml` (`npm ci` → `check:api` → `lint` → `typecheck` → `test` → `build`; Node 20 in CI). Added `gen:openapi`/`gen:api`/`check:api` scripts. Added `frontend/.gitattributes` (`* text=auto eol=lf`) so `openapi.json`/`schema.d.ts` are byte-identical across Windows/Linux and the `check:api` drift gate is stable.
- Deviations + why (real generated types differ from the plan's placeholder names):
  - **Wire-type names:** the plan mapped `Report`/`VerdictBlock`/`ArtifactMeta`, but the Phase-4 models generate as `ReportResponse`/`ArtifactResponse`/`JobRecord`/`JobList`. `types.ts` re-exports `Job=JobRecord`, `Report=ReportResponse`, `Artifact=ArtifactResponse`, plus `JobList`. **No `VerdictBlock`** exists (the engine Report is served as an opaque `dict`), so `Verdict` is deferred to the Task-9 `report-view.ts` view models rather than re-exported here.
  - **`ProgressEvent` hand-authored:** the WS progress frame is published out-of-band (Redis pub/sub → WS hub), so it is not in the REST OpenAPI and cannot be generated. It is the one hand-authored wire type in `types.ts`; its shape mirrors `workers/progress.RedisProgress.__call__` (`{job_id, step, pct, detail}`).
  - **Path param names:** FastAPI emits `/jobs/{job_id}`, `/reports/{report_id}`, `/artifacts/{artifact_id}` (not the plan's `{id}`); the client test and later hooks use the real param names.
  - **Client test rewritten for openapi-fetch 0.13:** the plan's test assumed an older API that passed a URL string to `fetch`. 0.13 captures `globalThis.fetch`/`Request` at `createClient()` time and hands `fetch` a `Request` object; undici's `Request` also rejects the relative `/api` base under Node. The test now stubs both globals + dynamic-imports the client (so the mock is captured), resolves path-absolute URLs against a dummy origin, and reads the URL off the `Request`. `client.ts` is unchanged (relative `/api`, correct for the browser + Vite proxy).
- **Verified:** from `frontend/` — `npm run test -- --run` → 2 files / 2 tests passed (Home + client). `npm run check:api` → `openapi-typescript` regenerates `schema.d.ts` with **no diff**. `npm run typecheck` clean; `npm run lint` → 0 errors.

### `feat(ui): scaffold Vite+TS+Tailwind+shadcn, routing shell, dev proxy`
- **Task 1.** Created the `frontend/` npm project (React 18 + Vite 5 + TypeScript strict): `package.json` (dev/build/typecheck/lint/test scripts), `vite.config.ts` (React plugin, `@/*` alias, dev proxy `/api`→`http://localhost:8000` with the `/api` prefix stripped + `/ws`→`ws://localhost:8000`, inline Vitest jsdom config), `tsconfig.json`/`tsconfig.node.json` (strict + `noUnusedLocals`/`noUnusedParameters`/`noFallthroughCasesInSwitch`, `@/*` path alias), `tailwind.config.ts` (`darkMode: "class"`) + `postcss.config.js`, `eslint.config.js` (flat config), `components.json` (shadcn). Added `src/main.tsx` (React root → `RouterProvider`), `src/router.tsx` (`createBrowserRouter`, `/` → `Layout`/`Home`), `src/index.css` (Tailwind directives), `src/test/setup.ts` (jest-dom + RTL cleanup), `src/components/Layout.tsx` (nav shell) + `src/pages/Home.tsx` (three engine entry-point cards). Extended the root `.gitignore` for `frontend/{dist,coverage,.vite,playwright-report,test-results}`.
- Deviations + why:
  - **Node 22.20.0** used (plan says Node 20 LTS); `engines.node` set to `>=20` so it accepts the installed 22 (a compatible superset) rather than pinning/rejecting it.
  - **Tailwind v3** pinned (`^3.4`) to match the plan's PostCSS/`@tailwind`-directive config model (v4's CSS-first config would break it).
  - **`shadcn init` not run** (interactive + network); `components.json` written by hand and `index.css` holds the `@tailwind base/components/utilities` directives. No shadcn UI components are consumed by Tasks 1–7, so no tokens were needed yet.
  - **tsconfig project-reference fix:** the plan's `tsconfig.json` both included `vite.config.ts` and referenced the composite `tsconfig.node.json` that owns it → TS6305/TS6310 under `tsc --noEmit`/`tsc -b`. Moved `vite.config.ts` ownership entirely to the node project (composite, emits to `node_modules/.tmp`) and dropped it from the root `include`. Both `tsc --noEmit` and `tsc -b && vite build` are clean.
  - **Home test scoped to `<main>`:** the plan's `getByRole("link", { name: /pack|detect|extract \+ scan/i })` matched the Layout nav links (including the "Packer" brand) as well as the Home cards → a multiple-match error. Queries are now scoped `within(getByRole("main"))` so they target the three Home cards, preserving the test's intent and the `<Layout>` wrapper.
- **Verified:** from `frontend/` — `npm run test -- --run` → 1 file / 1 test passed (Home). `npm run typecheck` (`tsc --noEmit`) clean. `npm run lint` (`eslint .`) → 0 errors. `npm run build` (`tsc -b && vite build`) → dist bundle built (209 KB js / 6.6 KB css).

---

## Phase 4 — API

### `test(api): add testcontainers integration + httpx API-E2E happy-path suites`
- **Task 15.** Added `tests/integration/api/conftest.py` — a session-scoped `_services` fixture spinning real `PostgresContainer("postgres:16-alpine", driver="psycopg")` + `RedisContainer("redis:7-alpine")`, and a `client` fixture that sets `PACKER_DB_DSN`/`PACKER_REDIS_URL`/`PACKER_STORE_ROOT`, runs `alembic upgrade head`, flips the Celery app to `task_always_eager` (submitted jobs run in-process against the real DB/Redis — no separate worker), and yields a `TestClient(create_app(...))`; plus `tiny_safetensors_ref`/`pickle_bytes`/`tiny_repo_zip`/`redis_url` fixtures. Added the three suites: `test_job_lifecycle.py` (a detect job persists + reaches a terminal state with its report queryable; an unsafe-pickle `POST /models` returns 422/400, never an uncaught 500), `test_ws_progress.py` (publish on the real `progress:{id}` channel → `ProgressHub` → `WS /ws/jobs/{id}` delivers it), and `test_api_e2e.py` (the spec §6 happy path `/pack`→poll→`/artifacts`→`/detect`→`/reports`). All modules are `pytestmark = pytest.mark.integration`.
- Deviations / environment notes:
  - **Docker is down on this host**, so the whole suite is unrunnable here — exactly the Phase-3 scan-E2E situation. The Docker gate is centralized in the `_services` fixture (`pytest.skip(...)` when `docker.from_env().ping()` fails), so every dependent test skips cleanly rather than erroring; testcontainers imports are done **inside** the fixtures so the conftest imports safely under `-m "not integration"`. In CI (daemon up) the `integration` job runs them.
  - Did **not** add `tests/integration/__init__.py` (the plan listed it) — the repo uses `--import-mode=importlib` and the sibling `tests/integration/{sandbox,detect}` dirs carry no `__init__.py`; adding one only under `integration/` would be inconsistent and is unnecessary for conftest/fixture discovery.
- **Verified:** `uv run pytest tests/integration/api -m integration` → **4 skipped** (Docker daemon down; 2 lifecycle + 1 WS progress + 1 API-E2E — hard gates in CI). `uv run pytest tests/unit` → **162 passed**. `uv run pytest -m "not integration"` → **162 passed, 10 deselected** (the 4 new + 6 Phase-3 integration tests), proving the integration conftest imports cleanly and nothing leaks into the fast suite. `uv run mypy src` clean (104 files); `uv run lint-imports` → **3 contracts kept, 0 broken**; ruff clean.

### `feat(api): add WebSocket progress hub + /ws/jobs/{id} endpoint`
- **Task 14.** Fleshed out `api/ws/hub.ProgressHub` (was the Task-1 placeholder holding just the redis client + prefix): `relay(job_id, send, *, max_messages=None)` subscribes Redis `progress:{job_id}`, forwards each `"message"` payload to the async `send` callable, and unsubscribes in `finally` — pure fan-out, no ML state (SYSTEM-DESIGN §3.6). The `max_messages` cap makes the relay deterministic in tests; production omits it and loops until disconnect. Added `routers/ws.py` — `WS /ws/jobs/{id}` accepts, reconciles by pushing the current `JobRecord` on connect (SYSTEM-DESIGN §5.7), then streams progress via `hub.relay(job_id, ws.send_text)` until `WebSocketDisconnect`.
- Deviations: none — the existing `tests/unit/fakes.FakeRedis`/`_FakePubSub` (async `pubsub().listen()` replay added back in Task 4) already matches the relay's contract, so the hub is exercised with a fake broker exactly per spec §6; `hub` dep param annotated `Any`.
- **Verified:** `uv run pytest tests/unit/api/test_ws_hub.py -v` → **1 passed** (two events published on `progress:j1` are drained + forwarded in order `["train","done"]`). Full `uv run pytest tests/unit` → **162 passed**. `uv run mypy src` clean (104 files); `uv run lint-imports` → **3 contracts kept, 0 broken**; ruff clean.

### `feat(api): add jobs/models/artifacts/reports read routers`
- **Task 13.** Filled the four read routers: `jobs.py` — `GET /jobs` (filters `status`,`type` → `JobList`) + `GET /jobs/{id}` (404 when missing); `reports.py` — `GET /reports/{id}` serving detect **and** scan uniformly through the shared `ReportResponse` (`id/job_id/kind/report`, spec §5); `artifacts.py` — `GET /artifacts/{id}` → `ArtifactResponse` (404 when missing); `models.py` — `GET /models` (list), `GET /models/{id}` (404), and `POST /models` validating `ModelCreate`, refusing non-safetensors formats up front with `UnsafeModelError` (→422 via the Task-7 handler) then inserting a `ModelRow` → `ModelRecord`.
- Deviations: repo-typed dep params are annotated `Any` (mypy-clean attribute access on the injected fakes/Sql repos alike). `POST /models` is a registration stub — the plan's "run the upload through `HFModelLoader` via the store" needs an actual file body; since the acceptance test posts JSON with no file, the route enforces the same safetensors-only **policy** (pickle → `UnsafeModelError` → 422) without loading, and records `sha256`/`path` as empty placeholders (the real hashing lands with multipart upload wiring in a later phase). No engine/ML logic in any handler.
- **Verified:** `uv run pytest tests/unit/api/test_routers_read.py -v` → **4 passed** (`GET /jobs/j1` → detect; `GET /jobs?type=detect` → 1 row; `GET /reports/r1` → shared model with `verdict=="UNLIKELY"`; missing job → 404). Full `uv run pytest tests/unit` → **161 passed**. `uv run mypy src` clean (104 files); `uv run lint-imports` → **3 contracts kept**; ruff clean.

### `feat(api): add pack/detect/extract/scan submit routers (validate->enqueue->return)`
- **Task 12.** Added `api/deps.py` — the injectable seams: `get_settings`/`get_session`/`get_job_service`/`get_report_repo`/`get_artifact_repo`/`get_model_repo`/`get_store`/`get_hub`/`get_broker`/`get_current_user` (auth stub), all overridable in tests. `get_broker` returns a `_CeleryBroker` whose `send_task(name, args, queue)` lazily imports `workers.celery_app.app` (broker abstracted so routes enqueue via a fake in tests). Added the four submit routers `pack.py`/`detect.py`/`extract.py`/`scan.py` — each does exactly **validate Pydantic request → persist a job → enqueue the routed Celery task → return the `JobRecord` (202)**, zero engine logic: `pack`→`gpu`, the rest→`default`. `/pack` reads the `UploadFile`, `store.put_blob`s it, and passes `{"root": ref}`; `/scan` relies on `ScanRequest`'s exactly-one-target validator (invalid body → 422). Wired `routers/include_routers()` to include all nine routers (lazy import avoids api↔workers cycles); added trivial `APIRouter` stubs for `jobs`/`models`/`artifacts`/`reports`/`ws` (filled in Tasks 13–14). Restructured `tests/unit/fakes.FakeBroker` to record `_SentTask(name, args, queue)`.
- Deviations: added the `python-multipart` runtime dep (FastAPI needs it for `UploadFile` on `/pack`). Added `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends"]` — the `= Depends(...)` default is the documented FastAPI idiom, not a B008 mutable-default bug (first route handlers with DI in the codebase). Injected deps (`store`/`broker`) are annotated `Any` (the plan left them bare) so `store.put_blob`/`broker.send_task` type-check under mypy strict.
- **Verified:** `uv run pytest tests/unit/api/test_routers_submit.py -v` → **3 passed** (`POST /detect` → 202 `queued`/`detect`, enqueues `detect.run`→`default`; `POST /pack` multipart → 202, enqueues `pack.run`→`gpu`; `POST /scan {}` → 422 from the one-target validator). Full `uv run pytest tests/unit` → **157 passed**. `uv run mypy src` clean (104 files); `uv run lint-imports` → **3 contracts kept**; ruff clean.

### `feat(workers): add generic run_engine_job wrapper + four one-line engine tasks`
- **Task 10.** Added `workers/runner.py` — `run_engine_job(job_id, engine_call, *, jobs, reports, artifacts, ports, redis_client)`, the ONE job-lifecycle wrapper (SYSTEM-DESIGN §5.7): bind correlation id → `mark_running` → build `RedisProgress` → `engine_call(ports, progress)` → `_persist_result` → `mark_succeeded`; `PackerError` → `mark_failed(code=e.code)` (no raise); unknown `Exception` → `mark_failed(code="internal")` + `_log.exception` + re-raise. `_persist_result` persists a `Report` (→ `report:{id}`), a pack `str` artifact id (opens the pak, inserts an `Artifact` → `artifact:{id}`), else `extraction:{...}`. Added `workers/tasks.py` — `pack_task`(→gpu)/`detect_task`/`extract_task`/`scan_task`(→default), one-liners over a shared `_run` that builds prod repos/ports/redis from Hydra. Added `workers/io.materialize_repo(store, ref)` (upload zip → temp dir, adapter-level IO). Extended `tests/unit/fakes.py` with `SyncFakeRedis`, `StubStore`, `FakeEnginePorts`.
- Deviations (adapting to the **actual** engine entry-point signatures):
  - `EngineCall` is typed `Callable[[Any, ProgressCallback], object]` (not the plan's `[EnginePorts, ...] -> Report | str`): `ports` is `Any` so the lambdas satisfy each engine's own structural port Protocol (`Detector._Ports` etc.) without `EnginePorts` failing the structural check, and the return is `object` to also cover extract's `Extraction`. `_persist_result` narrows with `isinstance` and `cast(Any, ports.store)`.
  - `ExtractionService.extract(target)` takes **only** an `ExtractTarget` (not `(target, cfg, ports)`); `ScanPipeline.run(target, cfg, ports)` takes `cfg == cfg.engine` (it reads `cfg.sandbox…`) and an `ExtractTarget` target. `extract_task`/`scan_task` build `ExtractTarget(model_ref=ModelRef.parse(spec["target"]), pak_path=…)` accordingly. `detect`/`extract`/`scan` ignore `pr` (their signatures take no progress arg).
  - **mypy:** added a scoped `[[tool.mypy.overrides]]` on `packer.workers.tasks` disabling `disallow_untyped_decorators` — celery's `@app.task` is an untyped decorator (no stubs); the task bodies stay fully typed. (Mirrors the existing celery `ignore_missing_imports` override.)
- **Verified:** `uv run pytest tests/unit/workers/test_runner.py -v` → **4 passed** (report persisted + `succeeded`; `PackerError`→`failed`/`unsafe_model` without raising; unknown→`failed`/`internal` + re-raise; progress bound as `RedisProgress` and published). `import packer.workers.tasks` registers `pack.run`/`detect.run`/`extract.run`/`scan.run`. Full `uv run pytest tests/unit` → **154 passed**. `uv run mypy src` clean (94 files); `uv run lint-imports` → **3 contracts kept** (`workers → api.db/api.repos/api.composition` legal; engine still framework-agnostic); ruff clean.

### `feat(api): add FilesystemArtifactStore + composition DI root (assemble_ports)`
- **Task 11.** Added `engine/common/stores/filesystem.py` — `FilesystemArtifactStore(root)` `@STORE_REGISTRY.register("filesystem")` implementing the `ArtifactStore` port (`put_pak`/`open_pak`/`put_blob`/`open_blob`/`exists`) over a root dir, reusing the canonical `.pak` layout via `PakWriter`/`PakReader` (stdlib + safetensors only). Added `api/composition.py` — `assemble_ports(cfg) -> EnginePorts`, the ONE DI root (SYSTEM-DESIGN §3.5/§5.7): `store = STORE_REGISTRY.create(cfg.store.name, **cfg.store.params)`, `loader = HFModelLoader()`, and (when `cfg.sandbox.runner` is set) `sandbox = SANDBOX_REGISTRY.create(...)`. Added the `conf/store/filesystem.yaml` group + `store: filesystem` default so `cfg.store.name`/`cfg.store.params.root` resolve.
- Deviations (adapting to the **actual** Phase-0 signatures + the import graph):
  - **Ordering:** committed before Task 10 — `workers/tasks.py` imports `api.composition.assemble_ports`, so composition must exist for `mypy src` / imports to stay green at Task 10's commit.
  - `HFModelLoader` takes `allow_pickle` **per-`load()` call**, not at construction (real Phase-0 loader), so the plan's `HFModelLoader(allow_pickle=...)` became `HFModelLoader()`; detect/extract load safetensors-only by default. `cfg.models.allow_pickle` is left as an unconsumed seam.
  - `import packer.engine.sandbox.adapters.docker` (not the empty `.adapters` package) actually triggers `@SANDBOX_REGISTRY.register("docker")`.
  - **import-linter:** added ONE documented `ignore_imports` edge to the "clean layering" contract — `common.stores.filesystem -> artifacts.pak` — mirroring the existing docker-adapter carve-out on the forbidden contract (the store lives under `common/stores/` per the §8 storage-backend playbook and reuses the canonical `.pak` layout instead of duplicating it; still stdlib+safetensors → engine stays framework-agnostic). All 3 contracts remain **kept**.
  - The composition test registers a no-daemon `_FakeSandboxRunner` under `"fake_sandbox"` and wires the DI root to it, because the real `DockerSandboxRunner` calls `docker.from_env()` at construction (raises `SandboxError` with the daemon down) — exactly the fake-runner substitution the plan authorizes for the unit env.
- **Verified:** `uv run pytest tests/unit/api/test_composition.py -v` → **3 passed** (filesystem `.pak` round-trip; `"filesystem"` registered; `assemble_ports` wires store+loader+sandbox with no live Docker). Real `load_settings()` resolves `store.name=="filesystem"`, `store.params.root`. Full `uv run pytest tests/unit` → **150 passed**. `uv run mypy src` clean (91 files); `uv run lint-imports` → **3 contracts kept, 0 broken**; ruff clean.

### `feat(workers): add RedisProgress ProgressCallback publishing to Redis`
- **Task 9.** Added `workers/progress.py` — `RedisProgress(job_id, client, *, prefix="progress:")` whose `__call__(*, step, pct, detail=None)` matches `packer.engine.common.progress.ProgressCallback` exactly and publishes a `ProgressEvent`-shaped JSON (`{job_id, step, pct, detail}`) to the `progress:{job_id}` channel. The engine stays Redis-agnostic (SYSTEM-DESIGN §3.6): the worker binds this bridge before calling the engine, so the engine never imports redis.
- Deviations: none (plan snippet used verbatim; `client: Any` keeps it broker-agnostic for the sync/async redis client alike).
- **Verified:** `uv run pytest tests/unit/workers/test_progress.py -v` → **1 passed** (publishes to `progress:job-1` with the exact JSON payload). `uv run mypy src` clean (88 files); ruff check + format clean.

### `feat(workers): add Celery app with Hydra broker config and queue routing`
- **Task 8.** Added `workers/celery_app.py` — `make_celery(cfg=None) -> Celery` reads broker/result-backend from Hydra (`cfg.broker`), sets `task_default_queue="default"` and `task_routes` (`pack.run`→`gpu`; `detect.run`/`extract.run`/`scan.run`→`default`, spec §4), flips `task_always_eager` from `cfg.broker.eager` (for in-process integration/E2E), and pins `worker_pool="solo"` (Windows-safe local dev; Linux workers override in compose). `app = make_celery()` module singleton. The `Celery(...)` constructor is lazy — no broker connection at import, so the routing test needs no live Redis.
- Deviations: added a `[[tool.mypy.overrides]] ignore_missing_imports` entry for `celery`/`celery.*` (it ships no py.typed/stubs — same pattern as docker/yara/transformers). The engine never imports celery (still enforced by the framework-agnostic contract).
- **Verified:** `uv run pytest tests/unit/workers/test_celery_routing.py -v` → **1 passed** (`pack.run`→gpu, others→default, `task_default_queue=="default"`). Full `uv run pytest tests/unit` → **146 passed**. `uv run mypy src` clean (87 files); `uv run lint-imports` → 3 contracts kept, 0 broken; ruff clean.

### `feat(api): map PackerError.code to HTTP problem+json responses`
- **Task 7.** Fleshed out the Task-1 `api/errors.py` stub: `code_to_status(code)` (`unsafe_model`→422, `config_error`→400, `load_error`→422, everything else→500) and `register_error_handlers(app)` installing a `PackerError` exception handler that renders an RFC-7807 `application/problem+json` body `{type, title, status, code, detail}`. Covers errors raised synchronously in routes (e.g. an unsafe-pickle rejection on upload); in-job engine errors become failed rows in Task 10.
- Deviations: the test imports only `UnsafeModelError` (the plan snippet also imported `ConfigError`/`PackerError` but never referenced them — dropped to stay F401-clean; the `config_error` path is asserted via the string literal exactly as the plan does).
- **Verified:** `uv run pytest tests/unit/api/test_errors.py -v` → **2 passed** (status mapping; `/boom` raising `UnsafeModelError` → 422 problem+json with `code=="unsafe_model"`, detail contains "pickle"). `test_app.py` still green (handler registration is a no-op on the boot path). `uv run mypy src` clean (86 files); ruff clean.

### `feat(api): add JobService with status transitions and input-hash dedup`
- **Task 6.** Added `api/jobs/service.py` — `JobService(repo, *, dedup=False)` with `create(type, input_ref=None, input_hash=None) -> JobRecord`, `get(id)`, `list(status=None, type=None)`. `correlation_id == job id` (SYSTEM-DESIGN §7); rows map to the `JobRecord` wire schema via `model_validate(..., from_attributes=True)`. When `dedup` is on and a **succeeded** job with the same `input_hash` exists, it is returned instead of creating a new one (spec §4). Pure orchestration — no engine logic.
- Deviations: none (plan snippet used verbatim modulo ruff import grouping).
- **Verified:** `uv run pytest tests/unit/api/test_job_service.py -v` → **3 passed** (create returns queued job with `correlation_id == id`; dedup-on reuses the succeeded job; dedup-off always mints a new id). `uv run mypy src` clean (86 files); `uv run lint-imports` → 3 contracts kept; ruff clean.

### `feat(api): add Pydantic v2 wire schemas for requests/responses`
- **Task 5.** Added `api/schemas/requests.py` (`PackRequest`/`DetectRequest`/`ExtractRequest`/`ScanRequest`/`ModelCreate`, all `extra="forbid"`; `ScanRequest` has an after-validator enforcing exactly one of `extraction_id`/`model_ref`) and `api/schemas/responses.py` (`JobRecord`/`JobList`/`ModelRecord`/`ArtifactResponse`/`ReportResponse`; the `_Resp` base sets `from_attributes=True` so ORM rows map straight through). Pydantic is the wire contract only (ADR-012).
- Deviations: the `dict` wire fields (`manifest_json`/`metrics_json`/`report`) are typed `dict[str, object]` (not the plan's bare `dict`) for mypy strict; the `_exactly_one_target` return annotation is the unquoted `ScanRequest` (safe under `from __future__ import annotations`, ruff-clean).
- **Verified:** `uv run pytest tests/unit/api/test_schemas.py -v` → **3 passed** (DetectRequest requires `model_ref`; ScanRequest accepts exactly one target; JobRecord maps from an ORM `Job`). `uv run mypy src` clean (84 files); ruff clean.

### `feat(api): add repository protocols, SQLAlchemy repos, in-memory fakes`
- **Task 4.** Added `api/repos.py` — the `JobRepository`/`ReportRepository`/`ArtifactRepository`/`ModelRepository` `Protocol` interfaces (the seam letting tests inject fakes). Added `api/db/repositories.py` — `SqlJobRepository` (create/get/list/mark_running/update_progress/mark_succeeded/mark_failed/find_by_hash over a `Session`) plus `SqlReportRepository`/`SqlArtifactRepository`/`SqlModelRepository`. Added `tests/unit/fakes.py` — dict-backed `InMemory{Job,Report,Artifact,Model}Repository` (constructing real ORM rows) plus `FakeRedis` (captures publishes + a minimal async pubsub replay) and `FakeBroker` (records `send_task(name, args=…)` enqueues by name). Extended the import-linter "clean layering" contract with `packer.api` as the top layer (preserving the engine-internal ordering exactly).
- Deviations: the Sql repos + fakes carry **full type annotations** (the plan's snippet elided them) — required by mypy strict. `FakeRedis`/`FakeBroker` are provided now (per the plan) for the downstream Tasks 9–14; the pubsub/broker shims are minimal and plausible, to be refined by whoever implements the WS relay (Task 14). ruff re-grouped `tests.unit.fakes` as a first-party import.
- **Verified:** `uv run pytest tests/unit/api/test_repositories.py -v` → **4 passed** (Sql + in-memory lifecycle parity: queued→running→progress→succeeded + find_by_hash; failed records `error_code`). Full `uv run pytest tests/unit` → **137 passed**. `uv run mypy src` clean (81 files); `uv run lint-imports` → 3 contracts kept, 0 broken; ruff clean.

### `feat(api): add Alembic env + baseline migration for the four tables`
- **Task 3.** Added `alembic.ini` (`script_location = alembic`, empty `sqlalchemy.url` filled by env.py), `alembic/env.py` (online-only; sources the DSN from Hydra `cfg.db.dsn` when the ini leaves it blank, else honors the caller-set url; `target_metadata = Base.metadata`), `alembic/script.py.mako`, and `alembic/versions/0001_baseline.py` — real `op.create_table(...)` for `jobs`/`models`/`artifacts`/`reports` mirroring the Task 2 columns (SQLite-compatible `String`/`Text`/`Float`/`JSON`/`DateTime(timezone=True)`), plus indexes on `input_hash`/`sha256`/`job_id` and a reversible `downgrade()`.
- Deviations: none material. `alembic/` sits at the repo root (outside `src/packer`), so it is not in the import-linter graph nor the `mypy src` scope; ruff still lints it and is clean (the `0001_baseline.py` numeric filename did not trip N999).
- **Verified:** `uv run pytest tests/unit/api/test_migrations.py -v` → **1 passed** (`alembic upgrade head` on a temp SQLite builds all four tables). `uv run mypy src` clean (79 files); `uv run lint-imports` → 3 contracts kept; ruff check + format clean on `alembic/`.

### `feat(api): add SQLAlchemy 2.0 typed models for jobs/models/artifacts/reports`
- **Task 2.** Added `api/db/base.py` (`Base(DeclarativeBase)` + `session_scope(factory)` transactional context manager for worker-side sessions) and `api/db/models.py` — the four SQLAlchemy 2.0 `Mapped[]`-typed models mirroring spec §3: `Job` (id/type/status/timestamps/correlation_id/input_ref/**input_hash**(dedup, indexed)/result_ref/error/**error_code**/progress_pct/progress_step), `ModelRow`, `Artifact`, `ReportRow`. `JSON` (not Postgres `JSONB`) so the same models drive SQLite in unit tests.
- Deviations: the JSON columns use `Mapped[dict[str, object]]` (not the plan snippet's bare `Mapped[dict]`) — mypy strict forbids the bare generic. `input_hash`/`error_code` are the documented spec-§3 extensions (config-gated dedup + clean `PackerError.code` mapping). `from collections.abc import Iterator` (ruff UP035).
- **Verified:** `uv run pytest tests/unit/api/test_db_models.py -v` → **2 passed** (Job round-trips on SQLite with `progress_pct` default 0.0; exactly `{jobs, models, artifacts, reports}` registered on `Base.metadata`). `uv run mypy src` → clean (79 files); ruff clean.

### `feat(api): add app factory, Hydra settings groups, deps (fastapi/celery/redis/sqlalchemy)`
- **Task 1.** Added the `packer.api` + `packer.workers` packages and the runtime/dev deps (fastapi, `uvicorn[standard]`, celery, redis, sqlalchemy, alembic, `psycopg[binary]`; dev: pytest-asyncio, httpx, testcontainers). Extended `engine/common/config_schema.py` with the `ApiCfg`/`DbCfg`/`BrokerCfg`/`LoggingCfg` structured configs (secrets via `${oc.env:...}`) and registered the `api`/`db`/`broker`/`logging` groups. Added the four minimal value files under `conf/{api,db,broker,logging}/` and wired them into `conf/config.yaml`'s defaults. Added `api/settings.load_settings()` (the one Hydra→settings entry point, ADR-012), `api/main.create_app()` (lazy SQLAlchemy engine + async Redis pool + `ProgressHub` opened in an async lifespan; `/health` returns `{"status":"ok"}`), and the lazy `routers/include_routers()` stub.
- Deviations from the plan snippets (adapting to the **actual** post-Phase-2/3 tree):
  - The plan's `conf/config.yaml` + `register_configs()` snapshots predate Phases 2/3, so they omit `engine/detect`/`engine/extract`. I **kept** those existing entries and only appended the four new groups/`cs.store` lines (as the plan's parenthetical instructs).
  - Created minimal **stubs** for two modules `main.py` imports that are fully implemented later: `errors.register_error_handlers` (no-op until Task 7) and `ws/hub.ProgressHub` (holds the redis client + prefix until the Task 14 relay) — without them the lifespan can't open and the `TestClient` boot test can't pass. Both are called out in their own task entries when fleshed out.
  - Used `from collections.abc import AsyncIterator` (ruff UP035) instead of the plan's `from typing import AsyncIterator`.
  - The API value yamls (`api/service.yaml` etc.) trigger Hydra's benign "validated against ConfigStore schema with the same name" 1.1→1.2 deprecation warning (schema + value file share a group/name); tests are green and this is the documented Hydra structured-config pattern.
- **Verified:** `uv run pytest tests/unit/api/test_app.py -v` → **2 passed** (health 200 `{"status":"ok"}`; `settings.api.port==8000`, `settings.broker.progress_prefix=="progress:"`). `uv run mypy src` → clean (76 files); `uv run lint-imports` → 3 contracts kept, 0 broken; ruff check + format clean.

## Phase 3 — Extractor + Sandbox

### `feat(sandbox): ScanReportBuilder + ScanPipeline emitting unified Report(kind=scan)`
- **Task 14.** Added `ScanReportBuilder` to `report/builders.py` — builds `Report(kind="scan")` on the shared Phase-2 `Report` model: `VerdictBlock(label=risk.verdict, ...)`, `ReportSection`s for static findings / dynamic behavior / per-file risk, and honest `limitations` (strace fidelity always; blind best-effort caveat + notes when `confidence_class == "blind"`; surfaced static/dynamic disagreements). Added `sandbox/pipeline.py` — `ScanPipeline.run(target, cfg, ports, progress)` runs the §5.5 flow (extract → static → dynamic per exec unit via the injected `ports.sandbox` → score → build) emitting semantic progress; raises `ScanError` if no sandbox port is injected. Added the Docker-backed E2E `tests/integration/sandbox/test_scan_e2e.py` + a `phase1_pak` conftest fixture for the integration dir.
- Deviations from the plan snippet (adapting to the **actual** Phase-2 `Report` model + the layering contract):
  - The real `ReportSection` is `title` + `body: dict[str, object]` (no `data=` kwarg, `body` is a dict not a string). `ScanReportBuilder` puts findings rows/counts and per-file scores into `body` accordingly.
  - `report` is a **lower** layer than `extract`/`sandbox`, so it must not import them (even under `TYPE_CHECKING`, which import-linter/grimp counts). Instead of the plan's `TYPE_CHECKING` imports of `Extraction`/`Finding`/`RiskReport`, the builder consumes them **structurally** via read-only `_ExtractionLike`/`_FindingLike`/`_RiskReportLike` Protocols — exactly the `VerdictLike` pattern already in `report/model.py`. Params use `Sequence[...]` (covariant) so `list[Finding]` fits.
  - E2E test guarded with a `_docker_available()` `skipif` (per the containment-test pattern) so the suite stays green when the daemon is down.
- **Verified:** `uv run pytest tests/unit/sandbox/test_pipeline.py` → 2 passed (malicious extraction → verdict in {suspicious,malicious} with sections; blind extraction adds the best-effort limitation). Full `uv run pytest tests/unit` → **128 passed**. `uv run pytest tests/integration/sandbox -m integration` → **5 skipped** (Docker daemon down on this host: 4 containment + 1 scan E2E; they are hard gates in CI / with Docker Desktop up). `uv run mypy src` clean (68 files); `uv run lint-imports` → 3 contracts kept; ruff clean.

### `feat(sandbox): RiskScorer calibrated verdict + static/dynamic disagreement surfacing`
- **Task 13.** Added `sandbox/scorer.py`: `RiskReport` (frozen: verdict/score/confidence/per_file/disagreements/findings) and `RiskScorer.score(static, dynamic, calib)` — weighted per-severity aggregation (max over files) → thresholded verdict (`benign`/`suspicious`/`malicious`) using the Hydra `RiskCfg` weights + thresholds. `_confidence` rises with static+dynamic corroboration; `_disagreements` surfaces static-only / dynamic-only high risk instead of hiding it. Added `calibrate()` (MVP no-op hook) + `evaluate()` (precision/recall/accuracy on a labeled set). Committed the two named disk fixtures `tests/fixtures/malware/{planted_malicious,benign_sample}.py`.
- Deviations: none functional; wrapped two long disagreement strings and used `float(calib.suspicious)` explicitly (ruff line-length + consistency). Excluded `tests/fixtures/` from ruff lint/format (`extend-exclude` + `--force-exclude` on the hooks) so the planted-malware sample and `.pak` artifacts are never rewritten.
- **Verified:** `uv run pytest tests/unit/sandbox/test_scorer.py` → 3 passed (planted malicious → `malicious` via real `ast_rules`/`yara_scan`/`secrets` scan; benign → `benign`; static-only disagreement surfaced); `uv run mypy src` clean (67 files); `uv run lint-imports` → 3 contracts kept; ruff clean; malware fixtures confirmed byte-unchanged by the format hook.

### `feat(extract): ExtractionService routes exact vs blind by manifest presence`
- **Task 12.** Added `extract/service.py`: `ExtractionService.extract(target) -> Extraction` — pure routing that picks `"exact"` when a manifest is present (`ModelRef.kind == "pak"`, or a directory containing `manifest.json`) and `"blind"` otherwise; the two extractors do the work.
- Deviation from plan snippet: added a local `_Extractor` Protocol and `cast(_Extractor, ...)` at the `EXTRACTOR_REGISTRY.create()` boundary so mypy-strict resolves `.extract` (incremental-ports pattern, same as Tasks 9/12 elsewhere).
- **Verified:** `uv run pytest tests/unit/extract` → 6 passed (exact chosen for `.pak` → byte-identical repo; blind chosen for a manifest-less dir); `uv run mypy src` clean (66 files); `uv run lint-imports` → 3 contracts kept; ruff clean.

### `feat(extract): BlindExtractor best-effort decode, clearly labeled non-exact`
- **Task 11.** Added `extract/blind.py`: `BlindExtractor` `@EXTRACTOR_REGISTRY.register("blind")` — no manifest, so it greedy-decodes from BOS via the forward-only `InferenceModel`, heuristically splits on `# FILE:` / `--- file:` boundary markers, and returns an `Extraction` with **low/medium confidence** (0.05–0.35) and explanatory `notes`; never claims byte-exactness and degrades to an empty/partial result (with a note) instead of crashing. `extract/__init__.py` now imports both `exact` and `blind`.
- Deviations: none (plan snippet used verbatim, ruff line-length reflow only). Since `transformers` is absent on this host, `from_model_ref` raises `ReconstructionError` and the extractor degrades to `files={}, confidence=0.05` — the intended graceful path (CI with transformers exercises the real decode).
- **Verified:** `uv run pytest tests/unit/extract/test_blind.py` → 2 passed (registered under "blind"; manifest-less model does not crash, labeled blind, confidence < 1.0, notes present); `uv run mypy src` clean (65 files); `uv run lint-imports` → 3 contracts kept; ruff clean.

### `feat(extract): Extraction/InferenceModel + ExactExtractor delegating to Phase-1 unpack`
- **Task 10.** New `engine/extract` subsystem: `model.py` (`Extraction`, `ExtractTarget` frozen VOs), `inference.py` (`InferenceModel` — forward-only wrapper: `from_pak` rebuilds the Phase-1 `TinyDecoder` + loads tensors; `from_model_ref` lazy-loads a foreign model via `transformers`; `next_logits` under `torch.no_grad()`), `exact.py` (`ExactExtractor` `@EXTRACTOR_REGISTRY.register("exact")`, byte-exact, confidence 1.0). Extended the import-linter "clean layering" contract to place `extract` above `pack`/`detect` (the `extract → pack` reuse edge). Committed a tiny `tests/fixtures/tiny_repo.pak` (epochs=1, CPU, 78 KB) that round-trips to `{main.py, util/helpers.py}`.
- Deviations from the plan snippet (Phase-1 API differs from the plan's assumptions, all faithful to the DoD "delegate to the Phase-1 Unpacker; no second decode path"):
  - `ExactExtractor.extract` **delegates to `pack.unpacker.unpack_bundle`** (the Phase-1 high-level decode) instead of hand-wiring `InferenceModel.from_pak` + `Unpacker.reconstruct`. The plan's wiring assumed a `pack.model.TinyDecoder.from_manifest` and a forward-only model usable by `Unpacker.reconstruct`; in the actual Phase-1, `Unpacker`/`InferenceModel` live in `pack.decode`, `TinyDecoder` in `pack.arch` (no `from_manifest`), and `TeacherForcedGreedy.reconstruct` needs `next_token`+`detokenize` (not `next_logits`). `unpack_bundle` reuses exactly the components the plan's self-review lists (Unpacker + TeacherForcedGreedy + DeltaVarintCodec + `MarkerCorpusSerializer.deserialize`), so this is a **stronger** "single decode path".
  - `InferenceModel.from_pak` builds the decoder from `manifest.model` fields directly (validating the five required dims → `ReconstructionError`), since `TinyDecoder.from_manifest` doesn't exist. It imports `TinyDecoder` from `pack.arch` (not `pack.model`). The extract `InferenceModel` is the forward-only inference point used by the **blind** path (Task 11); exact reuses Phase-1's own forward pass.
  - Added `transformers`/`transformers.*` to the mypy `ignore_missing_imports` override (optional lazy import; not installed here, so blind foreign-model load degrades to `ReconstructionError`).
  - Excluded `tests/fixtures/.*\.pak/` from the `end-of-file-fixer`/`trailing-whitespace` pre-commit hooks — they were rewriting the byte-exact `manifest.json`/`tokenizer.json`, which would break the round-trip.
- **Verified:** `uv run pytest tests/unit/extract/test_inference.py tests/unit/extract/test_exact.py` → 2 passed (forward-only shape; exact extraction byte-identical to the original repo, confidence 1.0); `uv run mypy src` clean (64 files); `uv run lint-imports` → 3 contracts kept (`extract → pack` now legal); ruff clean. Fixture round-trip re-verified during generation.

### `feat(sandbox): StaticAnalyzer iterates enabled_scanners via SCANNER_REGISTRY`
- **Task 9.** Added `StaticAnalyzer` to `sandbox/analyzers.py`: `scan(files, enabled) -> list[Finding]` resolves each name via `SCANNER_REGISTRY.create(name)` and aggregates findings. Open/closed — adding a scanner (new file + `enabled_scanners` entry) needs zero edits here; unknown names raise `ConfigError` (fail-fast) straight from the registry.
- Deviation from plan snippet: added a local `_Scanner` Protocol and `cast(_Scanner, ...)` at the `create()` boundary (the incremental-ports pattern — `SCANNER_REGISTRY` is `Registry[object]`), so mypy-strict resolves `.scan`.
- **Verified:** `uv run pytest tests/unit/sandbox/test_static.py` → 3 passed (aggregates enabled scanners, open/closed new scanner needs no edit, unknown → `ConfigError`); `uv run mypy src` clean (60 files); `uv run lint-imports` → 3 contracts kept; ruff clean.

### `feat(sandbox): YARA + secrets scanners with bundled rules`
- **Task 8.** Added `YaraScanner` (`yara_scan`, bundled `malware.yar` — obfuscated-exec + reverse-shell shapes) and `SecretsScanner` (`secrets`, regex sweep for private keys / AWS keys / generic tokens). `static/__init__.py` now self-registers all five scanners.
- Deviations: **yara-python is not installed** (no working Windows build; `uv add yara-python` didn't take) — so `yara_scan` **lazy-imports** yara and degrades to `yara.unavailable` (works with or without the native lib; installed in CI it matches real patterns). Extended the `detect-private-key` pre-commit exclude to cover `secrets.py` + `test_secrets.py` (they carry a non-real key header, as flagged in Phase 0). Added a `yara` mypy override.
- **Verified:** `pytest tests/unit/sandbox/static` → 13 passed (secrets flags private-key + AWS key, benign clean; yara degrades); mypy clean; ruff clean.

### `feat(sandbox): Bandit + Semgrep scanners (bundled rules, graceful degrade)`
- **Task 7.** Added `BanditScanner` (`bandit_scan`) and `SemgrepScanner` (`semgrep_scan`) — CLI subprocesses over a materialized copy of the extracted files (static-only, never executed on host), mapping tool severities to `Finding`s. Both **degrade gracefully** to an `info` "unavailable" marker on `FileNotFoundError`/timeout/bad-JSON. Semgrep uses a bundled local ruleset (no network). Shared `_util.materialize()` temp-dir helper.
- Deviation from plan snippet: **`uv add bandit` only, not semgrep** — semgrep has no Windows wheel (ADR-004 primary target); its scanner degrades to the `semgrep.unavailable` marker (installed in CI/Linux, it produces real findings). The test accepts either path.
- **Verified:** `pytest tests/unit/sandbox/static` → 8 passed (bandit yields a real finding for `shell=True`; semgrep degrades cleanly on Windows); mypy clean; ruff clean.

### `feat(sandbox): AST dangerous-construct scanner + self-registration pattern`
- **Task 6.** Added `sandbox/static/ast_rules.py`: `AstRulesScanner` `@SCANNER_REGISTRY.register("ast_rules")` — stdlib-`ast` detector for `eval`/`exec`/`compile`/`__import__`, `os.system`/`popen`/`exec*`, `subprocess`/`socket`/`ctypes`/`pickle`/`marshal`, mapped to severity-tagged `Finding`s; unparseable files → `ast.parse-error` info (no crash). `static/__init__.py` self-registers scanners on import (the pattern later scanners follow).
- Deviation from plan snippet: `ast.Import | ast.ImportFrom` union in `isinstance` (ruff UP038 modernization).
- **Verified:** `pytest tests/unit/sandbox/static/test_ast_rules.py` → 4 passed (eval+subprocess flagged high, benign clean, syntax error → info); mypy clean; ruff clean.

### `feat(sandbox): DynamicAnalyzer maps sandbox behavior to Findings`
- **Task 5.** Added `sandbox/analyzers.py`: `DynamicAnalyzer.analyze(unit, sandbox, policy) -> list[Finding]` — runs the unit through the injected sandbox port and maps behaviors to `dynamic.*` findings (network-attempt=high, fs-write=medium, timeout=medium, suspicious-syscall=low, trace-unavailable=info). Uses a local `_SandboxRunner` Protocol (sandbox-owned types can't be a kernel port). Unit-tested with a fake sandbox — no Docker.
- **Verified:** `pytest tests/unit/sandbox/test_dynamic.py` → 2 passed; mypy clean; ruff clean.

### `test(sandbox): containment security gate (net/fs/pid/time escapes must fail)`
- **Task 4.** Added `tests/integration/sandbox/test_containment.py` — the security gate (ADR-008): network blocked+recorded, out-of-tmpfs write fails (read-only root), fork-bomb hits pids-limit, infinite loop hits the wall-clock timeout. Added a **daemon-availability skip guard** so `-m integration` skips gracefully when Docker/the image is absent (rather than erroring).
- **Verified (this env, daemon down):** all 4 skip cleanly under `-m integration`; ruff clean. These become hard gates in CI / when Docker Desktop is running.

### `feat(sandbox): DockerSandboxRunner adapter with hardened policy + docker→SandboxError wrapping`
- **Task 3.** Added `sandbox/adapters/docker.py`: `DockerSandboxRunner` `@SANDBOX_REGISTRY.register("docker")` — the **only** module importing `docker`. Applies every hardened flag per run (`network_mode=none`, `read_only`, `mem_limit`, `nano_cpus`, `pids_limit`, `cap_drop=[ALL]`, `security_opt=no-new-privileges`, non-root `user`, tmpfs), streams the unit into tmpfs via tar, captures stdout/stderr + wall-clock timeout, pulls the `strace` trace and derives `syscalls`/`fs_writes`/`net_attempts` (degrades to empty on missing trace), and wraps all `docker.errors.*` into `SandboxError`. Added `uv add docker`.
- import-linter: added `docker` to the forbidden list with the **one** sanctioned adapter exception (`sandbox.adapters.docker -> docker`); extended layering with `sandbox` at the top. mypy override + targeted ignore for docker's incomplete stubs.
- **Verified (unit, fake client — no daemon):** `pytest tests/unit/sandbox/test_docker_runner.py` → 3 passed (registered, hardened flags applied, `docker.errors→SandboxError`); mypy clean; **import-linter 3 contracts kept**; ruff clean.

### `feat(sandbox): add SandboxPolicy/SandboxResult/ExecUnit/Finding/FileSet + hardened config`
- **Task 2.** Added sandbox value objects: `SandboxPolicy` (frozen, `.from_cfg`, all hardened flags), `SandboxResult`, `ExecUnit`, `Finding` (5-field contract), `FileSet` (`.from_extraction`/`.exec_units`, `.py`→python). Extended `SandboxCfg` (full hardened schema + `enabled_scanners` + nested `RiskCfg`), added `ExtractCfg`, registered both Hydra groups; added `engine/extract: default` to config defaults.
- Deviations: `FileSet.from_extraction` takes a structural `_HasFiles` Protocol (not `extract.Extraction`) so the sandbox needs no `extract` import; `test_fileset.py` deferred to Task 10 (needs `Extraction`); group YAMLs omitted (ConfigStore supplies defaults).
- **Verified:** `pytest tests/unit/sandbox/test_policy.py test_findings.py` → 3 passed (hardened flags from cfg, frozen); mypy clean; ruff clean.

### `feat(sandbox): add hardened Docker image (pinned py3.10 + strace, non-root)`
- **Task 1.** Added `docker/sandbox/Dockerfile` — `packer-sandbox:latest`, the **only** environment extracted (hostile) code may run in (ADR-008): pinned `python:3.10.19-slim-bookworm`, `strace` for syscall capture, non-root `sandbox` user (uid/gid 1000), `WORKDIR /scratch` (tmpfs at run), no network-capable entrypoint. Plus `.dockerignore`.
- **Environment note:** the Docker **daemon** (Docker Desktop Linux engine) is not running in this dev environment, so `docker build`/container runs can't be exercised here. The plan already treats image-build + containment as **integration steps** (no unit test); they run in CI / when Docker Desktop is up. Phase-3 **unit** tests use a fake Docker client (Task 3) and operate on code strings (scanners), so they need no daemon.

## Phase 2 — Detector

### `docs: mark Phase 2 complete`
- **Phase 2 done.** All 12 plan tasks landed across 13 commits on `phase-2-detector` (Tasks 10/11 executed in dependency order 11→10). Five inference-free weight signals + ensemble + calibration + `Detector.detect` + the shared `engine/report/` kernel; no-inference enforced three ways (structural `WeightAccessor`, import-linter torch-forbidden, behavioral gate). **93 unit tests, mypy-strict clean (45 files), 3 import-linter contracts kept, ruff clean.**
- Branch merged into `main` with `--no-ff`.
- **Next:** Phase 3 (Extractor + Sandbox) — exact + blind extraction (reusing Phase-1 `Unpacker`), Docker sandbox runner + containment gate, five scanners, risk scorer, `ScanPipeline`.

### `test(detect): add behavioral no-inference gate + enforce contracts (Phase 2 wrap-up)`
- **Task 12.** Added the behavioral no-inference gate (`test_no_inference_gate.py`): a fake model whose `forward`/`generate` raise; `Detector.detect` still returns a 5-section detect `Report`, proving detection never touches the forward path. Added the import-linter **"detect runs no inference"** contract and extended the layering to `{pack|detect} > {models|artifacts|report} > common`.
- Deviations / fixes:
  - import-linter can't forbid an external *subpackage* (`torch.nn.functional`) → forbade all of `torch` in `detect` (stronger: detect is torch-free). Synced DEVELOPMENT.md §3.1.
  - **pytest `--import-mode=importlib`**: `test_config.py` existed in both `common/` and `detect/`; the default prepend mode requires unique basenames. importlib mode identifies test modules by path — needed as subsystems multiply.
  - Fixed the Phase-0 `test_registries_exist_and_are_named` (asserted empty registries) — signals now self-register globally, so it asserts `.names()` shape, not emptiness.
  - Updated the `ports.py` growth-map doc to reflect that torch/subsystem-referencing ports live in their subsystems, not the kernel.
- **Verified:** **full `tests/unit` → 93 passed**; mypy clean (45 files); import-linter **3 contracts kept**; ruff check + format clean.

### `feat(detect): add Calibrator fit/calibrate + evaluate harness`
- **Task 10.** Extended `calibration.py`: `Calibrator.fit(labeled_scores)` (deterministic per-signal Fisher weighting + threshold midpoints), `Calibrator.calibrate(fixtures, *, loader)` (loads each fixture weights-only, runs signals, then fits — lazy-imports `run_signals` to avoid the runner↔calibration cycle), and `evaluate(labeled_scores, params) -> Metrics` (measured accuracy/precision/recall + memorized-vs-control separation). Added an **integration-marked** fixture test that **skips** when Phase-1 fixtures are absent.
- **Verified:** `pytest tests/unit/detect/test_calibration.py` → 2 passed (Fisher up-weights the separating signal; accuracy=1.0, separation>0 on synthetic rows); integration test skips cleanly; mypy clean; ruff clean.

### `feat(detect): add Detector.detect runner + run_signals helper`
- **Task 11** (done before Task 10 — the calibrator's `calibrate` imports `run_signals`). Added `detect/runner.py`: `Detector.detect(model_ref, cfg, ports) -> Report` — loads weights only → runs config-enabled signals via the registry → ensemble → `DetectReportBuilder`; falls back to `CalibrationParams.default()` when the version file is absent. Plus `run_signals(ref, *, loader, enabled)` reused by the calibrator. Structural `_Loader`/`_Ports`/`_DetectCfg`/`_Signal` Protocols keep `detect` decoupled from the loosely-typed `EnginePorts`/`DictConfig`.
- Deviation from plan snippet: a `_Signal` Protocol + `cast` at the `Registry[object]` boundary (`SIGNAL_REGISTRY.create(n).analyze` isn't typed otherwise).
- **Protocol fix (in `report/model.py`):** `VerdictLike`/`SignalResultLike` declared their members as settable attributes, which **frozen** dataclasses (`Verdict`, `SignalResult`) don't satisfy under mypy-strict. Changed them to **read-only `@property`** members, which match both frozen and mutable implementations.
- **Verified:** `pytest tests/unit/detect/test_runner.py tests/unit/report` → 5 passed (detect report has 5 sections + limitations; deterministic same-model output); mypy clean; ruff clean.

### `feat(detect): add Verdict, CalibrationParams/Store, Ensemble scorer + detect config`
- **Task 9.** Added `verdict.py` (`Verdict` + `LABEL_LIKELY/INCONCLUSIVE/UNLIKELY`), `calibration.py` value objects (`CalibrationParams.default()` + JSON round-trip, `Metrics`, `LabeledModel`, `CalibrationStore`), and `ensemble.py` (`Ensemble.score(results, calib)` — confidence- and per-signal-weighted, thresholded to a label; iterates results, names no concrete signal). Added `DetectCfg` to `config_schema.py` (registered under Hydra group `engine/detect`) and to `config.yaml` defaults.
- Deviation: `conf/engine/detect/ensemble.yaml` omitted (ConfigStore-registered `DetectCfg` supplies defaults, consistent with Phase 0/1).
- **Verified:** `pytest tests/unit/detect/test_ensemble.py test_config.py` → 4 passed (monotonic + labels, low-confidence discounting, store round-trip, config composes); mypy clean; ruff clean.

### `feat(report): add ReportBuilder base + DetectReportBuilder`
- **Task 8.** Added `report/builders.py`: `ReportBuilder` base (`_verdict_block` + `kind`) and `DetectReportBuilder.build(verdict, results) -> Report` — one section per signal, per-signal evidence, and the ADR-007 limitation notes (signature-not-proof, cannot-recover-code, cannot-distinguish-code-from-other-data). Consumes structural `VerdictLike`/`SignalResultLike`, so `report` still imports only `common`.
- **Verified:** `pytest tests/unit/report` → 3 passed; mypy clean; import-linter 2 contracts kept (no `report`→`detect`); ruff clean.

### `feat(report): add versioned Report model + JSON/text renderers`
- **Task 7.** Added the shared reporting kernel `engine/report/model.py` (reused by Phase 3): `Report{kind: detect|scan, schema_version, verdict, sections, evidence, limitations}` (frozen pydantic) with `to_json()`/`to_text()`; unknown `schema_version` raises `ConfigError`. Plus `VerdictBlock`, `ReportSection`, and structural `VerdictLike`/`SignalResultLike` Protocols so builders never import `detect` (keeps `report` importing only `common`).
- **Verified:** `pytest tests/unit/report/test_model.py` → 2 passed (JSON round-trip + text render, version guard); mypy clean; ruff clean.

### `feat(detect): add metadata signal + signal self-registration discovery`
- **Task 6.** Added `MetadataSignal` `@SIGNAL_REGISTRY.register("metadata")` — config/param heuristics (tiny param proxy, small vocab, `.pak`-shaped manifest markers → strong evidence). Filled `signals/__init__.py` so importing the package self-registers all five signals (open/closed discovery).
- Deviation: `contextlib.suppress(KeyError)` instead of try/except/pass (ruff SIM105).
- **Verified:** `pytest tests/unit/detect` → 12 passed (incl. registry discovers all five signals); mypy clean; ruff clean.

### `feat(detect): add effective/stable-rank signal`
- **Task 5.** Added `RankSignal` `@SIGNAL_REGISTRY.register("rank")` — mean effective-rank ratio (`effective_rank/full_rank`) across layers; low-rank (concentrated-spectrum) layers score higher.
- **Verified:** `pytest tests/unit/detect/test_rank.py` → 1 passed (low-rank scores higher than full-rank); mypy clean; ruff clean.

### `feat(detect): add embedding/unembedding structure signal`
- **Task 4.** Added `EmbeddingSignal` `@SIGNAL_REGISTRY.register("embedding")` — per-token embedding-norm distribution: normalized Shannon entropy (low = a few hot tokens) + dead-region fraction; concentrated embeddings score higher.
- **Verified:** `pytest tests/unit/detect/test_embedding.py` → 1 passed (`dead_fraction>0.9` on concentrated); mypy clean; ruff clean.

### `feat(detect): add weight-norm profile signal`
- **Task 3.** Added `WeightNormSignal` `@SIGNAL_REGISTRY.register("weight_norm")` — layerwise Frobenius-norm dispersion (coefficient of variation) + max/median inflation ratio; inflated layers score higher.
- **Verified:** `pytest tests/unit/detect/test_weight_norm.py` → 1 passed; mypy clean; ruff clean.

### `feat(detect): add spectral/RMT signal (MP outliers + heavy-tail alpha)`
- **Task 2.** Added `SpectralSignal` `@SIGNAL_REGISTRY.register("spectral")` — combines outlier-singular-value rate (vs. the MP bulk edge) and heavy-tail Hill alpha across attention + MLP matrices; empty model → score/confidence 0.
- **Verified:** `pytest tests/unit/detect/test_spectral.py` → 2 passed (rank-1 spikes score higher than random, `outlier_rate>=1`); mypy clean; ruff clean.

### `feat(detect): add SignalResult value object + spectral/rank numerics helpers`
- **Task 1.** Scaffolded `engine/detect/`: `SignalResult{name, score, confidence, evidence}` frozen value object and pure numerics helpers (`singular_values`, `frobenius_norm`, `spectral_norm`, `stable_rank`, `effective_rank`, `mp_upper_edge`, `estimate_sigma`, `count_outlier_singular_values`, `hill_alpha`) — all numpy, no torch.
- Deviations from plan snippet: typed matrices as `NDArray[Any]` (mypy-strict); replaced ambiguous Unicode (`×`,`–`) in docstrings (ruff RUF002).
- **Numerics fix:** the plan's median-based `estimate_sigma` under-read σ (0.845 vs true 1.0), pushing the MP edge below the bulk max → false outliers on random Gaussians. Replaced with the Frobenius estimate `σ = ‖W‖_F/√(nm)` (RMS of entries), robust to a few spikes. Verified across 10 seeds: **0 false positives on random matrices, 0 spike misses**.
- **Verified:** `pytest tests/unit/detect/test_numerics.py` → 5 passed; mypy clean; ruff clean.

## Phase 1 — Packer

### `docs: mark Phase 1 complete`
- **Phase 1 done.** All 12 plan tasks (+1 kernel refactor) landed across 14 commits on `phase-1-packer`. Definition of Done met: `pack → unpack` byte-identical over arbitrary bytes + `epochs=1` (residuals independent of convergence); in-process verify gate raises `PackError` before writing; honest manifest metrics (`artifact_bytes > gzip_bytes`); ≥3 memorized + ≥2 control fixtures; same-seed determinism; all four plugins self-register. **68 unit tests, mypy-strict clean (29 files), 2 import-linter contracts kept, ruff clean.**
- Branch merged into `main` with `--no-ff`.
- **Next:** Phase 2 (Detector) — five inference-free weight signals, ensemble + calibration, the shared `engine/report/` model, `Detector.detect`, and the no-inference gate.

### `feat(pack): add fixture generator (3 memorized paks + 2 control models)`
- **Task 12.** Added `scripts/make_fixtures.py`: `make_fixtures(out_dir)` writes 3 memorized `.pak` (from distinct synthetic repos) + 2 controls (random-init and normal-trained-on-noise, as safetensors dirs loadable via `HFModelLoader`) — the negatives Phase 2 calibrates against and Phase 3 extracts. Deterministic + tiny; not committed (weights stay out of git). Added `scripts/__init__.py` and `pythonpath = ["."]` to pytest config so `scripts` is importable in tests.
- **Verified:** `pytest tests/unit/pack/test_fixtures.py` → 1 passed (3 memorized paks round-trip, 2 controls load as safetensors); ruff clean.

### `test(pack): add byte-exact round-trip gates (arbitrary bytes, epochs=1, determinism)`
- **Task 11.** Added `test_roundtrip.py` — the CI correctness gates: (1) Hypothesis `pack → unpack` byte-identical over 25 arbitrary-byte examples (0–200 bytes); (2) byte-identical with `epochs=1` (residual mechanism proven independent of convergence); (3) two same-seed runs produce byte-identical `model.safetensors` / `residuals.bin` / `tokenizer.json`.
- **Verified:** `pytest tests/unit/pack/test_roundtrip.py` → 3 passed; ruff clean.

### `feat(pack): add Packer orchestrator with byte-exact verify gate and honest metrics`
- **Task 10.** Added `packer.py`: `Packer.pack(root, cfg, ports, progress) -> str` — serialize → tokenize → (reject if tokens > `context_len`) → build → train → capture residuals → **verify byte-exact round-trip in-process (fail-fast `PackError`)** → build manifest with honest metrics (`original`/`gzip`/`model`/`artifact` bytes, residual ratio, `lossless`) → persist (`ports.store.put_pak` or `PakWriter` under `cfg.out_dir`). Exported from `pack/__init__.py`.
- Deviations from plan snippet: typed `cfg` as `DictConfig` (eliminates ~15 `# type: ignore[attr-defined]` — OmegaConf attribute access is already `Any`) and cast the `Registry[object]` arch/decode lookups; widened `InferenceModel`'s `tokenizer` param to the `Tokenizer` port (it only calls `.decode`), so the registry-created tokenizer type-checks.
- **Test fix:** `test_pack_rejects_oversized_corpus` used `b"a"*5000`, which byte-BPE merges to <64 tokens (never trips the gate); replaced with ~6400 high-entropy (sha256-chained) bytes so the oversize gate is genuinely exercised.
- **Verified:** `pytest tests/unit/pack/test_packer.py` → 4 passed (pack↔unpack byte-exact + final `pct==1.0`; honest metrics with `artifact_bytes > gzip_bytes`; verify-gate raises on dropped residuals; oversize raises). Full `tests/unit/pack` → 35 passed; mypy clean; ruff clean; import-linter kept.

### `feat(pack): add standalone unpack()/unpack_bundle() reused by Phase 3`
- **Task 9.** Added `unpacker.py`: `unpack(pak_path)` and `unpack_bundle(bundle)` — read a `.pak`, rebuild the `TinyDecoder` from tensors + `ModelInfo`, wrap in `InferenceModel`, decode the residual blob via the registry-selected codec/decode strategy, and split frames → `{posix_relpath: bytes}`. Exported from `pack/__init__.py`; **reused verbatim by Phase 3's exact extractor**.
- Deviations from plan snippet: guarded the `int | None` manifest model fields with a single narrowing check (mypy-strict) before rebuilding; `cast(DecodeStrategy, DECODE_REGISTRY.create(...))` at the `Registry[object]` boundary; tensor param typed `dict[str, NDArray[Any]]`.
- **Verified:** `pytest tests/unit/pack/test_unpacker.py` → 2 passed (hand-built bundle + on-disk `.pak` both recover files byte-exact); mypy clean; ruff clean.

### `feat(pack): add InferenceModel, TeacherForcedGreedy decode, and shared Unpacker`
- **Task 8.** Added `decode.py` (the decode path **shared verbatim with Phase 3**):
  - `InferenceModel(model, tokenizer, bos_token_id)` — forward-only wrapper: `teacher_forced_preds`, `next_token`, `detokenize`.
  - `TeacherForcedGreedy` `@DECODE_REGISTRY.register("teacher-forced-greedy")` — deterministic self-correcting greedy decode (argmax, override from residuals).
  - `Unpacker(decode, codec)` — `reconstruct` / `reconstruct_blob`.
- Deviation from plan snippet: the `DecodeStrategy` Protocol is defined **in `decode.py`** (not imported from `common.ports`) because it references `InferenceModel`; concretized `.tolist()` returns for mypy-strict.
- **Verified:** `pytest tests/unit/pack/test_decode.py` → 4 passed — incl. **byte-exact reconstruction with an untrained model** (residual-guaranteed losslessness, ADR-006); mypy clean; ruff clean.

### `feat(pack): add DeltaVarintCodec + teacher-forced ResidualCapturer`
- **Task 7.** Added `residuals.py`: `DeltaVarintCodec` `@CODEC_REGISTRY.register("delta-varint-v1")` (sorts, delta-encodes positions, varints token ids; `decode(encode(r)) == r`) and `ResidualCapturer.capture(model, tokens)` → `[(pos, true_token)]` where teacher-forced argmax disagrees. Registered via `pack/__init__.py`.
- Deviation from plan snippet: `capture` types `model` as a local `_TeacherForced` Protocol (just `teacher_forced_preds`) instead of forward-referencing `InferenceModel` — avoids the residuals↔decode import cycle and keeps Task-7-before-Task-8 ordering clean.
- **Verified:** `pytest tests/unit/pack/test_residuals.py` → 5 passed (Hypothesis codec round-trip over 200 examples, mismatch capture); mypy clean; ruff clean.

### `feat(pack): add OverfitTrainer with determinism + progress reporting`
- **Task 6.** Added `trainer.py`: `OverfitTrainer.train(model, tokens, cfg, progress)` — AdamW teacher-forced overfit loop (no dropout), emits `step="train"` progress with epoch/loss/token-accuracy, no-ops on empty tokens. Module helpers `apply_determinism(seed, deterministic)` (seeds random/numpy/torch + deterministic flags) and `resolve_device(name)` (auto→cuda|cpu), reused by `Packer`. Added shared `tests/unit/pack/conftest.py` (`cfg_factory`).
- Deviations: `# type: ignore[no-untyped-call]` on `loss.backward()` (untyped in torch stubs); ruff RUF005 (`[bos, *tokens[:-1]]`) and B905 (`zip(..., strict=True)`) applied.
- **Verified:** `pytest tests/unit/pack/test_trainer.py` → 4 passed (loss decreases + progress emitted, same-seed determinism, empty-corpus no-op); mypy clean; ruff clean.

### `feat(pack): add from-scratch TinyDecoder + tiny-decoder architecture builder`
- **Task 5.** Added `arch.py`: `TinyDecoder(nn.Module)` — from-scratch causal decoder (token+positional embeddings, pre-norm blocks with `scaled_dot_product_attention(is_causal=True)`, GELU MLP, LM head) — and `TinyDecoderArch` `@ARCH_REGISTRY.register("tiny-decoder")` building it from config. Registered via `pack/__init__.py`.
- Added a `ModelArchitecture` Protocol **in `pack`** (not `common`): it references `torch.nn.Module`, so keeping it out of the kernel preserves the framework-light Dependency Rule (documented deviation from SYSTEM-DESIGN §3.2's placement).
- Deviations: `# noqa: N812` on the idiomatic `import torch.nn.functional as F`; `# type: ignore[attr-defined]` on OmegaConf attribute reads (per plan).
- **Verified:** `pytest tests/unit/pack/test_arch.py` → 3 passed (registered builder, forward shape `[1,8,64]`, eval determinism); mypy clean; ruff clean.

### `feat(pack): add byte-level BPE tokenizer (byte-bpe) with lossless coverage`
- **Task 4.** Added `tokenizer.py`: `ByteBPETokenizer` `@TOKENIZER_REGISTRY.register("byte-bpe")` — HF `tokenizers` BPE over a latin-1 byte↔char bijection with the full 256-symbol initial alphabet, so `decode(encode(x)) == x` for *any* bytes. Implements the enriched `Tokenizer` port + `from_bytes`/`_require`. Registered via `pack/__init__.py`.
- Deviations from plan snippet: concretized return values (`list(...)`, `int(...)`, typed `text: str`) to satisfy mypy-strict `warn_return_any`; `# type: ignore[no-untyped-call]` on `BpeTrainer` (untyped in the `tokenizers` stubs); tightened the pre-train test to `pytest.raises(PackError)` (ruff B017).
- **Verified:** `pytest tests/unit/pack/test_tokenizer.py` → 6 passed (lossless on training text + arbitrary 256-byte binary, serialization round-trip); mypy clean; ruff clean.

### `refactor(common): preserve concrete type in Registry.register; enrich Tokenizer port`
- Prep for the Phase-1 plugins (kernel change discovered when first using the decorator):
  - `Registry.register` is now generic in the **decorated** class (`_C`), not the registry's `T`. Before, `@REG.register(...) class Foo` collapsed `Foo`'s type to `type[T]`, erasing its concrete API — which would have broken `decode.py`/`unpacker.py` calling `ByteBPETokenizer`'s non-port methods (`bos_id`, `from_bytes`) in mypy-strict `src`. Now the decorated symbol keeps its concrete type; `create` still returns `T`.
  - `Tokenizer` port gained `vocab_size()`, `bos_id()`, `to_bytes()` — the methods `Packer` needs from any tokenizer plugin, so it stays plugin-agnostic (uses `TOKENIZER_REGISTRY.create(...)` without casting to the concrete class).
- **Verified:** `pytest tests/unit/common` green; mypy clean; import-linter kept.

### `feat(pack): add reversible MarkerCorpusSerializer + SerializedCorpus`
- **Task 3.** Added `corpus.py`: `SerializedCorpus` frozen value object (`bytes`, `file_map` of `(posix_relpath, start, end)`, `.n_files`/`.original_bytes`) and `MarkerCorpusSerializer` — deterministic (sorted posix paths), self-delimiting magic-framed serialize + fully reversible deserialize; corrupt framing raises `PackError`.
- **Verified:** `pytest tests/unit/pack/test_corpus.py` → 4 passed (nested/binary/empty/unicode-path files, determinism, span integrity, corruption); mypy clean.

### `feat(pack): extend TinyDecoderCfg with plugin-name + training fields`
- **Task 2.** Extended `TinyDecoderCfg` with backward-compatible defaulted fields: plugin selectors (`arch`, `tokenizer`, `decode`, `codec`) + training/persistence knobs (`weight_decay`, `seed`, `bos_token_id`, `out_dir`). Compose + override verified under `cfg.engine.pack`.
- Deviation from plan: the `conf/engine/pack/tiny_decoder.yaml` group file is omitted (as in Phase 0 Task 10, the ConfigStore-registered structured config supplies defaults); test uses the corrected dotted override `engine.pack.seed=7`.
- **Verified:** `pytest tests/unit/common/test_config_pack.py` → 2 passed; mypy clean.

### `feat(pack): scaffold pack package, add torch+tokenizers, add varint util`
- **Task 1.** Added runtime deps `torch>=2.13.0` (CPU build) and `tokenizers>=0.23.1` via `uv add`. Created the `packer.engine.pack` package (empty `__init__.py`; plugin-registration imports appended per task) and `varint.py` (`_write_uvarint`/`_read_uvarint` — unsigned LEB128, shared by corpus + residual codec).
- **Verified:** `pytest tests/unit/pack/test_varint.py` → 3 passed; mypy clean; import-linter kept (pack imports only stdlib so far).

## Phase 0 — Foundations

### `docs: mark Phase 0 complete`
- **Phase 0 done.** All 12 plan tasks landed across 14 commits on `phase-0-foundations`. Definition of Done fully met: 27 unit tests, mypy-strict clean (19 files), 2 import-linter contracts kept, all engine subpackages import with no side effects. (CI job is valid but unexercised — no remote yet.)
- Branch merged into `main` with `--no-ff`.
- **Next:** Phase 1 (Packer) — from-scratch tiny decoder, byte-BPE tokenizer, overfit trainer, residual capture, lossless `Packer.pack`.

> **Task order note:** remaining Phase-0 tasks are executed **11 → 12 → 10 → 9** (models, artifacts, config/assembler, import-linter). The import-linter layering contract references `packer.engine.models`/`artifacts`, so it must land *after* those packages exist; models & artifacts are independent of config/assembler.

### `chore: enforce Dependency Rule with import-linter contracts`
- **Task 9** (Phase-0 finale). Appended `[tool.importlinter]` to `pyproject.toml` with the Phase-0 contract subset:
  - **"engine is framework-agnostic"** (forbidden): `packer.engine` must not import `packer.api`, `packer.workers`, `redis`, `sqlalchemy`, `fastapi`, or `celery`.
  - **"clean layering"** (layers): `packer.engine.models | packer.engine.artifacts` sit above `packer.engine.common`; `common` imports nothing higher, and `models`/`artifacts` don't import each other.
- Added `include_external_packages = true` (required because the forbidden lists name external frameworks) — this was the one non-obvious knob; without it import-linter errors out.
- Added a local `import-linter` pre-commit hook (`uv run lint-imports`); synced `DEVELOPMENT.md` §3.1/§3.2.
- Later phases extend these toward the canonical end-state (detect no-inference, the docker adapter carve-out, and the extract/sandbox/api layers) as those modules land.
- **Verified:** `uv run lint-imports` → **2 contracts kept, 0 broken** (33 files, 60 dependencies analyzed).

### `feat(common): add Hydra config tree, structured configs, assembler skeleton`
- **Task 10.** Added:
  - `conf/config.yaml` — root Hydra config; `defaults` select `engine/pack: tiny_decoder` + `engine/sandbox: docker` (resolved from the ConfigStore); `run_dir` via `${oc.env:...}` interpolation.
  - `config_schema.py` — structured `@dataclass` configs `TinyDecoderCfg`, `SandboxCfg`; `register_configs()` stores them in the ConfigStore; `compose_config(overrides=...)` composes the root config via `initialize_config_dir`.
  - `assembler.py` — `EnginePorts` frozen dataclass (`store`/`sandbox`/`loader`) + `assemble_ports(cfg)` DI root (registry-driven; returns null ports until adapters register in later phases).
- Deviations from plan snippet: (a) `_CONF_DIR` uses `parents[4]` not `parents[3]` — `conf/` is at the repo root under the root src-layout; (b) test override syntax is `engine.pack.epochs=999` (dotted value override), not the plan's `engine/pack.epochs=999`; (c) the group option YAMLs (`tiny_decoder.yaml`/`docker.yaml`) are omitted — the ConfigStore-registered structured configs supply the defaults (files added when a phase needs file-level overrides); (d) dropped the unused `field` import.
- **Verified:** `pytest tests/unit/common/test_config.py` → 4 passed; ruff clean; `mypy src` clean.

### `chore: run ruff/mypy as local uv hooks to eliminate version drift`
- Converted ruff, ruff-format, and mypy pre-commit hooks from pinned mirror repos (`ruff-pre-commit@v0.5.0`, `mirrors-mypy@v1.10.0`) to **local `uv run` hooks**, so the hook uses the exact `uv.lock` versions (ruff 0.15.20, mypy 2.2.0) — identical to CI.
- **Root cause:** the pinned ruff v0.5.0 didn't enforce `RUF022` (`__all__` sort) the way the uv-locked ruff 0.15.20 does, so `artifacts/codec.py` passed the hook in Task 12 but failed `uv run ruff check` afterward. Fixed `codec.py`'s `__all__` order (`["ResidualCodec", "Residuals"]`).
- Bumped `pre-commit/pre-commit-hooks` v4.6.0 → v5.0.0 (silences the deprecated-stage-name warning). Updated the canonical config in `DEVELOPMENT.md` §3.2.
- **Verified:** `pre-commit run --all-files` → all hooks pass.

### `feat(artifacts): add versioned Manifest, residual codec interface, PakReader/Writer`
- **Task 12.** Added the `.pak` artifact contract:
  - `common/types.py` — `Residuals = list[tuple[int, int]]` (kernel home per SYSTEM-DESIGN §3.1).
  - `common/ports.py` — `ResidualCodec` port (references the kernel `Residuals`); `CODEC_REGISTRY` tightened to `Registry[ResidualCodec]`.
  - `artifacts/manifest.py` — versioned pydantic `Manifest` (+ `ModelInfo`, `FileSpan`, `CorpusInfo`, `DecodeInfo`, `ResidualInfo`, `Metrics`); `to_json`/`from_json`; unknown `pak_version` raises `ConfigError` (propagates out of the validator, not wrapped by pydantic).
  - `artifacts/codec.py` — thin re-export site (`Residuals`, `ResidualCodec`) for artifact-oriented callers; concrete `DeltaVarintCodec` arrives in Phase 1.
  - `artifacts/pak.py` — `PakBundle` value object + `PakWriter`/`PakReader`, the only code that knows the on-disk layout (a directory: `model.safetensors`, `tokenizer.json`, `residuals.bin`, `manifest.json`).
- Deviation from plan snippet: `Residuals`/`ResidualCodec` live in the kernel (not `artifacts/codec.py`) so the port never inverts the Dependency Rule; `codec.py` re-exports them. Tensor maps typed `dict[str, NDArray[Any]]`.
- **Fix:** anchored the `.gitignore` ML-output ignores (`/data/`, `/artifacts/`, `/models_store/`) to the repo root — the unanchored `artifacts/` was shadowing the new source package `src/packer/engine/artifacts/` and `tests/unit/artifacts/`.
- **Verified:** `pytest tests/unit/artifacts` → 3 passed; **full `tests/unit` → 23 passed**; ruff clean; `mypy src` clean.
- **Task 11.** Added `src/packer/engine/models/`:
  - `loader.py` — `LoadedModel` frozen value object (`tensors`, `config`, `source`, `format`) + `HFModelLoader` (safetensors-first; `.bin`/`.pkl`/`.pt`/`.pth`/`.ckpt` without `allow_pickle=True` raises `UnsafeModelError`; missing safetensors raises `LoadError`). HF-hub download deferred to Phase 2.
  - `accessor.py` — `WeightAccessor`: role-based, tensor-only view (`attention_matrices`, `mlp_matrices`, `embedding`, `unembedding` with tied-weight fallback, `config`). No `forward`/`generate` — the structural half of the no-inference guarantee.
- Deviation from plan snippet: typed tensor maps as `dict[str, NDArray[Any]]` and configs as `dict[str, Any]` (mypy-strict rejects bare `np.ndarray`/`dict`). No new port added — `ModelLoader` port is deferred to Phase 2 (first consumer) to keep the Dependency Rule strict (a `common` port referencing the `models`-owned `LoadedModel` would invert the layering).
- **Verified:** `pytest tests/unit/models` → 4 passed; ruff clean; `mypy src` clean.

### `feat(common): add structured logging with correlation-id context`
- **Task 8.** Added `src/packer/engine/common/logging.py`: `get_logger(name)` (attaches a correlation-id filter once), `bind_correlation_id(cid)` / `current_correlation_id()` backed by a `ContextVar`, and `_CorrelationFilter` which stamps every record with the current id (or `-`).
- **Verified:** `pytest tests/unit/common/test_logging.py` → 2 passed; ruff clean; `mypy src` clean.

### `feat(common): add value-object types, port protocols, registry instances`
- **Task 7.** Added:
  - `types.py` — `ModelRef` frozen value object (`kind` = `hf`/`path`/`pak`) + `ModelRef.parse` heuristic (`.pak` → paths → HF id).
  - `ports.py` — port Protocols (SYSTEM-DESIGN §3.2): `ProgressCallback` (re-exported), `Clock`, `Rng`, `Tokenizer`.
  - `registries.py` — all nine canonical `Registry` instances (`TOKENIZER`, `CODEC`, `STORE`, `ARCH`, `DECODE`, `SIGNAL`, `SCANNER`, `SANDBOX`, `EXTRACTOR`).
- **Deviation — incremental ports (important, affects later phases):** mypy-strict errors on any forward reference to a type that doesn't exist yet (verified empirically). The plugin ports reference subsystem types that legitimately live in later phases (e.g. `Signal`→`SignalResult`, `Scanner`→`FileSet`/`Finding`, `SandboxRunner`→`ExecUnit`, `DecodeStrategy`→`InferenceModel` [torch]). So the port **catalog is introduced incrementally**, mirroring the project's existing incremental import-linter policy. Growth map is documented in `ports.py`:
  - Phase 0 T11 (models) adds `ModelLoader`; T12 (artifacts) adds `ArtifactStore`, `ResidualCodec`.
  - Phase 1 adds `ModelArchitecture`, `DecodeStrategy`; Phase 2 adds `Signal`; Phase 3 adds `Scanner`, `SandboxRunner`, `Extractor`.
  - Each registry is typed `Registry[object]` until its port lands, then the annotation is tightened (runtime object is unchanged, so callers are unaffected). `TOKENIZER_REGISTRY` is already typed `Registry[Tokenizer]`.
  - **Downstream note:** when I reach Phases 1–3 I will add each port to `ports.py` + tighten its registry annotation, rather than assume the full catalog exists from Phase 0.
- **Verified:** `pytest tests/unit/common/test_types.py` → 4 passed; ruff clean (auto-sorted `__all__`); `mypy src` clean.

### `feat(common): add generic Registry[T] plugin mechanism`
- **Task 6.** Added `src/packer/engine/common/registry.py`: `Registry[T]` (the single plugin/extensibility mechanism) with `.register(name)` decorator, `.create(name, **kwargs) -> T`, `.names()`. Duplicate registration and unknown lookup both raise `ConfigError`.
- Deviation from plan snippet: imported `Callable` from `collections.abc` (ruff UP035; `typing.Callable` is deprecated).
- **Verified:** `pytest tests/unit/common/test_registry.py` → 3 passed; ruff clean; `mypy src` clean.

### `feat(common): add ProgressCallback protocol + recording/null impls`
- **Task 5.** Added `src/packer/engine/common/progress.py`: `ProgressEvent` (frozen dataclass `{step, pct, detail}`), `ProgressCallback` runtime-checkable Protocol (keyword-only `step`/`pct`/`detail`), `null_progress` no-op default, and `RecordingProgress` test double capturing `.events`.
- Deviation from plan snippet: dropped the unused `field` import (ruff F401).
- **Verified:** `pytest tests/unit/common/test_progress.py` → 3 passed; ruff clean; `mypy src` clean.

### `feat(common): add PackerError taxonomy`
- **Task 4.** Added `src/packer/engine/common/errors.py`: `PackerError(message, *, context)` base carrying a stable machine `code` and a safe `context` dict, plus `ConfigError`, `LoadError`, `UnsafeModelError(LoadError)`, `PackError`, `ReconstructionError`, `ScanError`, `SandboxError` — each with a default `code`.
- Deviation from plan snippet: typed `context` as `dict[str, object]` (bare `dict` fails mypy-strict `disallow_any_generics`). Same parametrization will be applied to other plan snippets that use bare `dict`.
- **Verified:** `pytest tests/unit/common/test_errors.py` → 3 passed; ruff clean; `mypy src` clean.

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
