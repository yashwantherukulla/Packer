# Phase 5 — Web UI (Part 4)

> **Goal:** an operator console over the API — drive all three engines, watch jobs live, and read reports.
> **Depends on:** Phase 4. **Blocks:** Phase 6 (E2E).
> **Part mapping:** Part 4.

---

## 1. Scope

**In scope**
- React 18 + Vite + TypeScript SPA.
- Screens: **Pack**, **Detect**, **Extract + Scan**, **Jobs**, **Reports**.
- Upload flows (repo zip for pack; model file / HF id for detect/extract).
- Live job progress via WebSocket.
- Report viewers: Detect (per-signal breakdown, verdict, confidence, limitation note) and Scan (risk verdict, static findings table, dynamic behavior, static/dynamic disagreement).
- Typed API client generated from the Phase-4 OpenAPI spec.

**Out of scope**
- Auth UI (stubbed). Multi-user dashboards, theming beyond a clean default. Mobile-first layouts (desktop-first is fine).

---

## 2. Structure

```
frontend/src/
├── pages/        Pack.tsx · Detect.tsx · ExtractScan.tsx · Jobs.tsx · Report.tsx
├── components/   Uploader · JobProgress · SignalBreakdown · FindingsTable · VerdictBadge · ...
├── api/          generated OpenAPI client + typed wrappers
├── hooks/        useJob(id) · useJobProgress(id) [WS] · useSubmitPack/Detect/Scan
└── lib/          ws client, formatting, risk/verdict color scales
```

- **Server state:** TanStack Query (polling `/jobs/{id}` + cache); **progress:** WebSocket via `useJobProgress`. WS is the live channel; Query is the source of truth on reconnect.
- **Styling:** Tailwind + shadcn/ui. Verdicts/risk use a consistent, accessible color scale (light + dark), applied uniformly across detect and scan reports.

---

## 3. Key flows

**Pack:** drop a repo zip → optional advanced config (epochs, model size) → submit → `JobProgress` streams training loss/epoch → on success, show artifact card with **honest size metrics** (original vs. gzip vs. artifact) and a download link.

**Detect:** pick model (HF id / upload / existing artifact) → submit → progress → **Detect report**: overall verdict + confidence, per-signal cards with evidence, and the explicit "signature not proof; cannot recover code" note (ADR-007).

**Extract + Scan:** pick model (+ artifact for exact mode) → submit → progress → show reconstructed file tree (exact = "byte-exact ✓"; blind = "best-effort, confidence: …") → **Scan report**: risk badge, static findings table (severity/rule/file/line), dynamic behavior (syscalls summary, fs writes, blocked net), and any static/dynamic disagreement callout.

**Jobs:** list with status filters; click through to the live/finished job and its report.

---

## 4. Integration points

- **Generated client from OpenAPI** keeps the UI types in lockstep with the API; regenerate on API change (documented script).
- **WebSocket** to `/ws/jobs/{id}` for progress; reconnect + fall back to polling.
- **Shared report shape** means one `Report` renderer handles both detect and scan kinds.
- Dev proxy: Vite proxies `/api` + `/ws` to the FastAPI service; production served behind the same origin (Phase 6 compose).

---

## 5. Testing plan

- **Component/unit (Vitest + RTL):** Uploader validation, `JobProgress` state rendering, `FindingsTable` sorting/severity, `VerdictBadge` mapping, report renderers with fixture JSON.
- **Contract:** the generated client compiles against the current OpenAPI; a smoke test hits a mocked API.
- **E2E (Playwright):** the three happy paths against a running stack — pack a tiny repo, detect a fixture, extract+scan a fixture — asserting progress appears and the report renders. These become part of the Phase-6 E2E gate.
- **Accessibility smoke:** keyboard nav + basic ARIA on primary controls.

---

## 6. Development steps (ordered)

1. Vite + TS + Tailwind + shadcn/ui scaffold; routing; API base + WS client in `lib/`.
2. Generate the API client from OpenAPI; typed hooks.
3. `JobProgress` + `useJobProgress` (WS) against a real job.
4. Pack page + Uploader + artifact card (with honest metrics).
5. Detect page + `SignalBreakdown` report viewer.
6. Extract+Scan page + file tree + `FindingsTable` + dynamic behavior viewer.
7. Jobs list.
8. Vitest + Playwright suites.

---

## 7. Acceptance criteria (milestone gate)

- [ ] A user can drive Pack, Detect, and Extract+Scan entirely from the browser.
- [ ] Job progress streams live via WebSocket, with polling fallback on reconnect.
- [ ] Detect and Scan reports render with verdict, confidence, and evidence; the Detect limitation note is shown.
- [ ] Artifact card shows honest size metrics (original / gzip / artifact).
- [ ] Playwright covers the three happy paths against a running stack.

---

## 8. Risks

- **API/UI type drift** → generate the client from OpenAPI; CI check that it's up to date.
- **WS flakiness** → reconnect + Query polling fallback; test both.
- **Report shape churn** → freeze the shared `Report` model in Phase 2/3; version it.
