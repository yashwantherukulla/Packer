# Phase 5 — Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the operator console over the Phase-4 API — a React SPA that drives all three engines (Pack, Detect, Extract+Scan), streams live job progress over WebSocket, and renders both report kinds through one unified viewer. Every screen and component the Phase-6 Playwright E2E gate consumes is produced here, on typed contracts generated from the API's OpenAPI spec.

**Architecture:** Delivery ring of the hexagon (SYSTEM-DESIGN §1, §5.8). The frontend depends **only** on the API's OpenAPI contract — no Python, no engine knowledge. Layered feature-oriented structure: `lib/` (framework-agnostic clients + color scale + formatters) → `api/` (generated OpenAPI client + typed wrappers) → `hooks/` (TanStack Query data-fetching + WS subscription) → `components/` (dumb, presentational, fixture-testable) → `pages/` (composition only). Server state is TanStack Query (source of truth, polls `/jobs/{id}`); live progress is WebSocket (`/ws/jobs/{id}`); Query is authoritative on reconnect (SYSTEM-DESIGN §5.7 ws/hub, ADR-011). One `ReportView` renders detect + scan reports, branching only on `report.kind` (SYSTEM-DESIGN §5.6).

**Tech Stack:** React 18 + Vite + TypeScript (strict), React Router 6, TanStack Query v5, Tailwind CSS + shadcn/ui, native WebSocket, `openapi-typescript` + `openapi-fetch` (generated client), Vitest + React Testing Library (unit/component), Playwright (E2E happy paths). Node 20 LTS, npm. Windows-native primary dev target (ADR-004).

## Global Constraints

*Every task's requirements implicitly include this section. Values copied verbatim from the specs/ADRs.*

- **TypeScript strict.** `tsconfig` `strict: true` + `noUnusedLocals`/`noUnusedParameters`/`noFallthroughCasesInSwitch`. `npm run typecheck` (`tsc --noEmit`) is green before every commit. No `any` that escapes a module boundary.
- **npm for the frontend, not uv.** All frontend work happens under `frontend/` with its own `package.json`/`package-lock.json` and Node 20 (DEVELOPMENT §1). uv/Python is not involved in this phase.
- **Components are dumb and presentational; hooks own data.** A component takes typed fixture props and renders — no `fetch`, no Query, no WS inside a component. All server state lives in `hooks/` (TanStack Query) and the WS subscription lives in `useJobProgress` (SYSTEM-DESIGN §5.8). This is what makes components trivially unit-testable with fixture props.
- **Types are generated from the API OpenAPI — never hand-written.** `src/api/schema.d.ts` is emitted by `openapi-typescript` from the committed `openapi.json`; wire types are re-exported (not re-declared) from `src/api/types.ts`. A CI step (`npm run check:api`) regenerates and `git diff --exit-code`s the result, so API/UI type drift fails the build (spec §8, §4). The only hand-authored types allowed are **presentational view models** over opaque `evidence`/section `data` payloads (the `dict` carve-out, SYSTEM-DESIGN §11).
- **One `ReportView`, `kind`-branch only.** The single report renderer branches on `report.kind` (`"detect" | "scan"`) and nothing else; verdict block and limitations are shared across both (SYSTEM-DESIGN §5.6). Do not special-case beyond `kind`.
- **WS live progress with Query polling fallback on reconnect.** `useJobProgress(id)` subscribes to `/ws/jobs/{id}`; on socket loss it surfaces `connected=false` and the UI advances from the Query-polled job row (`progress_pct`/`progress_step`) until the socket reconnects (spec §8 R2, ADR-011).
- **Desktop-first.** Clean default theme, light + dark. No mobile-first layouts; no auth UI (stubbed); no multi-user dashboards (spec §1 out-of-scope).
- **Accessible, consistent color scale.** Verdict/risk/severity tones map through one scale in `lib/verdict.ts`, applied uniformly across detect and scan, legible in light and dark (spec §2).
- **Conventional Commits**, one logical change per commit, `feat(ui)/test(ui)/chore(ui)` scopes.

## File Structure

```
frontend/
  package.json · package-lock.json           # npm project (Node 20)
  index.html
  vite.config.ts                              # React plugin + dev proxy (/api, /ws) + Vitest config
  tsconfig.json · tsconfig.node.json          # strict TS + @/* path alias
  tailwind.config.ts · postcss.config.js
  eslint.config.js
  openapi.json                                # committed snapshot of the Phase-4 OpenAPI spec
  playwright.config.ts
  src/
    main.tsx                                  # React root; RouterProvider + QueryClientProvider
    router.tsx                                # createBrowserRouter route table
    index.css                                 # Tailwind entrypoint
    test/setup.ts                             # RTL + jest-dom + afterEach cleanup
    lib/
      verdict.ts                              # verdict/risk/severity → tone → Tailwind classes
      format.ts                               # formatBytes · formatPct · formatRatio
      ws.ts                                   # createJobProgressSocket (reconnect + backoff)
      report-view.ts                          # presentational view models over report sections
    api/
      schema.d.ts                             # GENERATED by openapi-typescript (do not hand-edit)
      client.ts                               # openapi-fetch typed client (baseUrl /api)
      types.ts                                # re-exported wire types (Report, Verdict, Job, ...)
    hooks/
      useJob.ts                               # useJob(id) · useJobs(filters) · useReport(id) · useArtifact(id)
      useSubmit.ts                            # useSubmitPack · useSubmitDetect · useSubmitScan
      useJobProgress.ts                       # WS live + Query polling fallback
    components/
      Layout.tsx · Home.tsx-nav shell
      Uploader.tsx · JobProgress.tsx
      VerdictBadge.tsx · SignalBreakdown.tsx
      FindingsTable.tsx · BehaviorPanel.tsx
      ReportView.tsx · PackResultCard.tsx
    pages/
      Home.tsx · Pack.tsx · Detect.tsx · ExtractScan.tsx · Jobs.tsx · JobDetail.tsx · Report.tsx
  e2e/
    pack.spec.ts · detect.spec.ts · scan.spec.ts
.github/workflows/frontend.yml                # gen-check + lint + typecheck + unit + build
```

---

### Task 1: Vite + TS + Tailwind + shadcn scaffold, routing shell, dev proxy

**Files:**
- Create: `frontend/package.json`, `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/tailwind.config.ts`, `frontend/postcss.config.js`, `frontend/eslint.config.js`, `frontend/components.json` (shadcn)
- Create: `frontend/src/main.tsx`, `frontend/src/index.css`, `frontend/src/router.tsx`, `frontend/src/test/setup.ts`
- Create: `frontend/src/components/Layout.tsx`, `frontend/src/pages/Home.tsx`
- Test: `frontend/src/pages/Home.test.tsx`

**Interfaces:**
- Consumes: the Phase-4 API at `http://localhost:8000` (proxied).
- Produces: a running Vite dev server that proxies `/api` → FastAPI and `/ws` → the WebSocket hub; `npm run dev` / `test` / `typecheck` / `build` all runnable; a `Layout` nav shell + `Home` landing route.

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/Home.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Home } from "@/pages/Home";

test("home renders the three engine entry points", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Layout>
        <Home />
      </Layout>
    </MemoryRouter>,
  );
  expect(screen.getByRole("heading", { name: /packer console/i })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /pack/i })).toHaveAttribute("href", "/pack");
  expect(screen.getByRole("link", { name: /detect/i })).toHaveAttribute("href", "/detect");
  expect(screen.getByRole("link", { name: /extract \+ scan/i })).toHaveAttribute("href", "/scan");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/pages/Home.test.tsx`
Expected: FAIL — cannot resolve `@/components/Layout` / `@/pages/Home` (modules don't exist).

- [ ] **Step 3: Scaffold + implement**

Bootstrap: `npm create vite@latest frontend -- --template react-ts`, then add deps:
```bash
npm i react-router-dom @tanstack/react-query openapi-fetch
npm i -D tailwindcss postcss autoprefixer @vitejs/plugin-react vitest jsdom \
        @testing-library/react @testing-library/user-event @testing-library/jest-dom \
        openapi-typescript eslint typescript-eslint @playwright/test
npx shadcn@latest init -d          # writes components.json + base tokens
```

`frontend/vite.config.ts` (React plugin, `@/*` alias, dev proxy, Vitest config in one file):
```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    proxy: {
      // FastAPI serves /pack, /detect, ... at the root; strip the /api prefix.
      "/api": { target: "http://localhost:8000", changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
  },
});
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] },
    "types": ["vitest/globals", "@testing-library/jest-dom", "node"]
  },
  "include": ["src", "vite.config.ts", "playwright.config.ts"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`frontend/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

`frontend/tailwind.config.ts` — `content: ["./index.html", "./src/**/*.{ts,tsx}"]`, `darkMode: "class"`; `src/index.css` holds the `@tailwind base/components/utilities` directives (shadcn tokens appended by `init`).

`frontend/src/components/Layout.tsx`:
```tsx
import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/pack", label: "Pack" },
  { to: "/detect", label: "Detect" },
  { to: "/scan", label: "Extract + Scan" },
  { to: "/jobs", label: "Jobs" },
];

export function Layout({ children }: { children?: ReactNode }) {
  return (
    <div className="min-h-screen bg-white text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <header className="border-b">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="font-bold">Packer</NavLink>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to}
              className={({ isActive }) => (isActive ? "font-medium underline" : "text-slate-500")}>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children ?? <Outlet />}</main>
    </div>
  );
}
```

`frontend/src/pages/Home.tsx`:
```tsx
import { Link } from "react-router-dom";

const CARDS = [
  { to: "/pack", title: "Pack", body: "Overfit a tiny decoder to memorize a repo into a .pak artifact." },
  { to: "/detect", title: "Detect", body: "Weight-only memorization signature — no inference." },
  { to: "/scan", title: "Extract + Scan", body: "Reconstruct code and score it in a hardened sandbox." },
];

export function Home() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Packer console</h1>
      <div className="grid gap-4 sm:grid-cols-3">
        {CARDS.map((c) => (
          <Link key={c.to} to={c.to} className="rounded-lg border p-4 hover:bg-slate-50 dark:hover:bg-slate-900">
            <h2 className="font-semibold">{c.title}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{c.body}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
```

`frontend/src/router.tsx` (routes grow in later tasks):
```tsx
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Home } from "@/pages/Home";

export const router = createBrowserRouter([
  { path: "/", element: <Layout />, children: [{ index: true, element: <Home /> }] },
]);
```

`frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
);
```

Add `package.json` scripts:
```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "typecheck": "tsc --noEmit",
  "lint": "eslint .",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/pages/Home.test.tsx && npm run typecheck`
Expected: PASS + typecheck clean. `npm run build` produces a bundle.

- [ ] **Step 5: Commit**
```bash
git add frontend
git commit -m "feat(ui): scaffold Vite+TS+Tailwind+shadcn, routing shell, dev proxy"
```

---

### Task 2: Generated OpenAPI client + CI up-to-date check

**Files:**
- Create: `frontend/openapi.json` (committed snapshot exported from the Phase-4 API)
- Create: `frontend/src/api/schema.d.ts` (GENERATED — never hand-edited), `frontend/src/api/client.ts`, `frontend/src/api/types.ts`
- Create: `.github/workflows/frontend.yml`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: the Phase-4 OpenAPI document (`GET http://localhost:8000/openapi.json`).
- Produces: a typed `api` client (`api.GET("/jobs/{id}", ...)` etc.) whose paths/schemas are generated; re-exported wire types `Job`, `Report`, `Verdict`, `Artifact`, `ProgressEvent`; an `npm run check:api` gate that fails on drift.

- [ ] **Step 1: Write the failing test**

`frontend/src/api/client.test.ts`:
```ts
import { afterEach, expect, test, vi } from "vitest";
import { api } from "@/api/client";

afterEach(() => vi.unstubAllGlobals());

test("client issues typed GET /jobs/{id} against the /api base and parses JSON", async () => {
  const fetchMock = vi.fn(async () =>
    new Response(JSON.stringify({ id: "j1", type: "detect", status: "succeeded" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  const { data, error } = await api.GET("/jobs/{id}", { params: { path: { id: "j1" } } });

  expect(error).toBeUndefined();
  expect(data?.status).toBe("succeeded");
  expect(String(fetchMock.mock.calls[0][0])).toContain("/api/jobs/j1");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/api/client.test.ts`
Expected: FAIL — `@/api/client` and `@/api/schema` don't exist yet.

- [ ] **Step 3: Generate + implement**

Export and commit the spec, then generate types:
```bash
# refresh the committed snapshot from a running API, then generate the typed schema
curl -s http://localhost:8000/openapi.json -o frontend/openapi.json
npx openapi-typescript ./frontend/openapi.json -o ./frontend/src/api/schema.d.ts
```

Add scripts to `frontend/package.json`:
```json
"gen:openapi": "curl -s http://localhost:8000/openapi.json -o openapi.json",
"gen:api": "openapi-typescript ./openapi.json -o ./src/api/schema.d.ts",
"check:api": "npm run gen:api && git diff --exit-code -- src/api/schema.d.ts"
```

`frontend/src/api/client.ts`:
```ts
import createClient from "openapi-fetch";
import type { paths } from "./schema";

// baseUrl "/api" pairs with the Vite proxy rewrite so generated paths ("/jobs/{id}")
// resolve to /api/jobs/{id} in the browser and /jobs/{id} at the FastAPI service.
export const api = createClient<paths>({ baseUrl: "/api" });
```

`frontend/src/api/types.ts` (re-export only — no hand-authored wire shapes):
```ts
import type { components } from "./schema";

export type Job = components["schemas"]["JobRecord"];
export type Report = components["schemas"]["Report"];
export type Verdict = components["schemas"]["VerdictBlock"];
export type Artifact = components["schemas"]["ArtifactMeta"];
export type ProgressEvent = components["schemas"]["ProgressEvent"];
```
*(Schema names track the Phase-4 Pydantic models; adjust the right-hand `["schemas"][...]` keys to whatever the generated `schema.d.ts` exposes — do not invent shapes, only reference generated ones.)*

`.github/workflows/frontend.yml`:
```yaml
name: frontend
on: [push, pull_request]
defaults:
  run: { working-directory: frontend }
jobs:
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - run: npm run check:api        # fails if src/api/schema.d.ts is stale vs committed openapi.json
      - run: npm run lint
      - run: npm run typecheck
      - run: npm run test
      - run: npm run build
  # Playwright E2E runs on a nightly / pre-release job (Phase 6), not every PR.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/api/client.test.ts && npm run check:api`
Expected: PASS; `check:api` reports no diff (schema is freshly generated + committed).

- [ ] **Step 5: Commit**
```bash
git add frontend/openapi.json frontend/src/api .github/workflows/frontend.yml frontend/package.json
git commit -m "feat(ui): generate typed OpenAPI client + CI drift check"
```

---

### Task 3: lib — verdict/risk color scale + formatters

**Files:**
- Create: `frontend/src/lib/verdict.ts`, `frontend/src/lib/format.ts`
- Test: `frontend/src/lib/verdict.test.ts`, `frontend/src/lib/format.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `verdictTone(label)` / `riskTone(label)` / `severityTone(sev)` → `Tone` and `toneClasses: Record<Tone, string>` (accessible light + dark). Detect labels `MEMORIZED-CODE-LIKELY|INCONCLUSIVE|UNLIKELY` (ARCHITECTURE §5.3); scan `malicious|suspicious|benign`; severity `critical|high|medium|low`.
  - `formatBytes(n)`, `formatPct(frac)`, `formatRatio(r)`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/verdict.test.ts`:
```ts
import { expect, test } from "vitest";
import { riskTone, severityTone, toneClasses, verdictTone } from "@/lib/verdict";

test("detect verdict labels map to tones", () => {
  expect(verdictTone("MEMORIZED-CODE-LIKELY")).toBe("danger");
  expect(verdictTone("INCONCLUSIVE")).toBe("warn");
  expect(verdictTone("UNLIKELY")).toBe("ok");
});

test("scan risk + severity map to tones", () => {
  expect(riskTone("malicious")).toBe("danger");
  expect(riskTone("benign")).toBe("ok");
  expect(severityTone("high")).toBe("danger");
  expect(severityTone("low")).toBe("ok");
});

test("every tone has light + dark classes", () => {
  for (const tone of ["danger", "warn", "ok", "neutral"] as const) {
    expect(toneClasses[tone]).toContain("dark:");
  }
});
```

`frontend/src/lib/format.test.ts`:
```ts
import { expect, test } from "vitest";
import { formatBytes, formatPct, formatRatio } from "@/lib/format";

test("formatBytes scales units", () => {
  expect(formatBytes(512)).toBe("512 B");
  expect(formatBytes(1536)).toBe("1.5 KB");
  expect(formatBytes(180_000)).toBe("175.8 KB");
});

test("formatPct + formatRatio", () => {
  expect(formatPct(0.25)).toBe("25%");
  expect(formatRatio(39.2)).toBe("39.2×");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/lib/verdict.test.ts src/lib/format.test.ts`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

`frontend/src/lib/verdict.ts`:
```ts
export type Tone = "danger" | "warn" | "ok" | "neutral";

export function verdictTone(label: string): Tone {
  switch (label.toUpperCase()) {
    case "MEMORIZED-CODE-LIKELY": return "danger";
    case "INCONCLUSIVE": return "warn";
    case "UNLIKELY": return "ok";
    default: return "neutral";
  }
}

export function riskTone(label: string): Tone {
  switch (label.toLowerCase()) {
    case "malicious": return "danger";
    case "suspicious": return "warn";
    case "benign": return "ok";
    default: return "neutral";
  }
}

export function severityTone(sev: string): Tone {
  switch (sev.toLowerCase()) {
    case "critical":
    case "high": return "danger";
    case "medium": return "warn";
    case "low": return "ok";
    default: return "neutral";
  }
}

export const toneClasses: Record<Tone, string> = {
  danger: "bg-red-100 text-red-900 border-red-300 dark:bg-red-950 dark:text-red-100 dark:border-red-800",
  warn: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950 dark:text-amber-100 dark:border-amber-800",
  ok: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-100 dark:border-emerald-800",
  neutral: "bg-slate-100 text-slate-900 border-slate-300 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700",
};
```

`frontend/src/lib/format.ts`:
```ts
export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(1)} ${units[i]}`;
}

export function formatPct(frac: number): string {
  return `${Math.round(frac * 100)}%`;
}

export function formatRatio(r: number): string {
  return `${r.toFixed(1)}×`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/lib/verdict.test.ts src/lib/format.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/verdict.ts frontend/src/lib/format.ts frontend/src/lib/verdict.test.ts frontend/src/lib/format.test.ts
git commit -m "feat(ui): add verdict/risk color scale + byte/pct formatters"
```

---

### Task 4: lib — WebSocket progress client (reconnect + backoff)

**Files:**
- Create: `frontend/src/lib/ws.ts`
- Test: `frontend/src/lib/ws.test.ts`

**Interfaces:**
- Consumes: the generated `ProgressEvent` type (Task 2).
- Produces: `createJobProgressSocket(jobId, handlers, opts) -> { close }`. Opens `ws(s)://<host>/ws/jobs/{id}`, parses each frame as `ProgressEvent`, reconnects with exponential backoff up to `maxRetries`, and reports open/close (with `willReconnect`) so the hook can flip to polling. Injectable `url()` + timing for tests.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/ws.test.ts`:
```ts
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { createJobProgressSocket } from "@/lib/ws";

class MockWS {
  static last: MockWS | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn(() => this.onclose?.());
  constructor(public url: string) { MockWS.last = this; }
}

beforeEach(() => { vi.stubGlobal("WebSocket", MockWS as unknown as typeof WebSocket); vi.useFakeTimers(); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

test("parses frames and reconnects on unexpected close", () => {
  const onEvent = vi.fn();
  const onClose = vi.fn();
  createJobProgressSocket("j1", { onEvent, onClose }, { baseDelayMs: 100, maxRetries: 2, url: (id) => `ws://x/ws/jobs/${id}` });

  const sock = MockWS.last!;
  sock.onopen?.();
  sock.onmessage?.({ data: JSON.stringify({ step: "train", pct: 0.5, detail: "epoch 100" }) });
  expect(onEvent).toHaveBeenCalledWith({ step: "train", pct: 0.5, detail: "epoch 100" });

  sock.onclose?.();                       // server dropped us
  expect(onClose).toHaveBeenCalledWith(true);
  vi.advanceTimersByTime(100);            // backoff elapses → a new socket opens
  expect(MockWS.last).not.toBe(sock);
});

test("caller close() suppresses reconnect", () => {
  const handle = createJobProgressSocket("j1", { onEvent: vi.fn() }, { url: (id) => `ws://x/${id}` });
  const sock = MockWS.last!;
  handle.close();
  const after = MockWS.last;
  vi.advanceTimersByTime(10_000);
  expect(MockWS.last).toBe(after);        // no new socket created
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/lib/ws.test.ts`
Expected: FAIL — `@/lib/ws` missing.

- [ ] **Step 3: Implement**

`frontend/src/lib/ws.ts`:
```ts
import type { ProgressEvent } from "@/api/types";

export type ProgressHandlers = {
  onEvent: (e: ProgressEvent) => void;
  onOpen?: () => void;
  onClose?: (willReconnect: boolean) => void;
};

export type Socket = { close: () => void };

type Opts = { maxRetries?: number; baseDelayMs?: number; url?: (id: string) => string };

function defaultUrl(jobId: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/jobs/${jobId}`;
}

export function createJobProgressSocket(jobId: string, handlers: ProgressHandlers, opts: Opts = {}): Socket {
  const maxRetries = opts.maxRetries ?? 5;
  const baseDelay = opts.baseDelayMs ?? 500;
  const makeUrl = opts.url ?? defaultUrl;

  let retries = 0;
  let closedByCaller = false;
  let ws: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    ws = new WebSocket(makeUrl(jobId));
    ws.onopen = () => {
      retries = 0;
      handlers.onOpen?.();
    };
    ws.onmessage = (msg: MessageEvent) => {
      try {
        handlers.onEvent(JSON.parse(String(msg.data)) as ProgressEvent);
      } catch {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      if (closedByCaller) return;
      const willReconnect = retries < maxRetries;
      handlers.onClose?.(willReconnect);
      if (willReconnect) {
        const delay = baseDelay * 2 ** retries;
        retries++;
        timer = setTimeout(connect, delay);
      }
    };
    ws.onerror = () => ws?.close();
  };

  connect();

  return {
    close: () => {
      closedByCaller = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    },
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/lib/ws.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/ws.ts frontend/src/lib/ws.test.ts
git commit -m "feat(ui): add WebSocket job-progress client with reconnect backoff"
```

---

### Task 5: hooks — Query provider + useJob/useJobs/useReport/useArtifact + useSubmit*

**Files:**
- Modify: `frontend/src/main.tsx` (wrap with `QueryClientProvider`)
- Create: `frontend/src/hooks/queryClient.ts`, `frontend/src/hooks/useJob.ts`, `frontend/src/hooks/useSubmit.ts`
- Test: `frontend/src/hooks/useJob.test.tsx`, `frontend/src/hooks/useSubmit.test.tsx`

**Interfaces:**
- Consumes: the `api` client (Task 2).
- Produces:
  - `useJob(id)` — GET `/jobs/{id}`, auto-polls (1.5s) while `queued|running`, stops when terminal (the polling source of truth, ADR-011). `useJobs(filters)`, `useReport(id)` (GET `/reports/{id}`), `useArtifact(id)` (GET `/artifacts/{id}`); the last three accept `string | null` and are disabled on `null`.
  - `useSubmitPack()` (multipart FormData → POST `/pack`), `useSubmitDetect()` / `useSubmitScan()` (JSON `{ model_ref }` → POST `/detect` / `/scan`); each returns the created `Job` and invalidates the jobs list.

- [ ] **Step 1: Write the failing tests**

`frontend/src/hooks/useJob.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useJob } from "@/hooks/useJob";

vi.mock("@/api/client", () => ({
  api: { GET: vi.fn(async () => ({ data: { id: "j1", type: "detect", status: "succeeded" } })) },
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    {children}
  </QueryClientProvider>
);

afterEach(() => vi.clearAllMocks());

test("useJob fetches and returns the job row", async () => {
  const { result } = renderHook(() => useJob("j1"), { wrapper });
  await waitFor(() => expect(result.current.data?.status).toBe("succeeded"));
});
```

`frontend/src/hooks/useSubmit.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useSubmitDetect } from "@/hooks/useSubmit";

const POST = vi.fn(async () => ({ data: { id: "job-9", type: "detect", status: "queued" } }));
vi.mock("@/api/client", () => ({ api: { POST } }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

afterEach(() => vi.clearAllMocks());

test("useSubmitDetect posts model_ref and yields a job", async () => {
  const { result } = renderHook(() => useSubmitDetect(), { wrapper });
  act(() => result.current.mutate({ model_ref: "Qwen/Qwen2.5-0.5B" }));
  await waitFor(() => expect(result.current.data?.id).toBe("job-9"));
  expect(POST).toHaveBeenCalledWith("/detect", { body: { model_ref: "Qwen/Qwen2.5-0.5B" } });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/hooks/useJob.test.tsx src/hooks/useSubmit.test.tsx`
Expected: FAIL — hook modules missing.

- [ ] **Step 3: Implement**

`frontend/src/hooks/queryClient.ts`:
```ts
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000, refetchOnWindowFocus: false } },
});
```

`frontend/src/main.tsx` (add the provider around the router):
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/hooks/queryClient";
import { router } from "./router";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </React.StrictMode>,
);
```

`frontend/src/hooks/useJob.ts`:
```ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Artifact, Job, Report } from "@/api/types";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    enabled: id !== "",
    queryFn: async (): Promise<Job> => {
      const { data, error } = await api.GET("/jobs/{id}", { params: { path: { id } } });
      if (error) throw error;
      return data as Job;
    },
    // Poll while active; this is the source of truth the WS layer falls back to.
    refetchInterval: (q) => (TERMINAL.has((q.state.data as Job | undefined)?.status ?? "") ? false : 1500),
  });
}

export function useJobs(filters: { status?: string; type?: string } = {}) {
  return useQuery({
    queryKey: ["jobs", filters],
    queryFn: async (): Promise<Job[]> => {
      const { data, error } = await api.GET("/jobs", { params: { query: filters } });
      if (error) throw error;
      return data as Job[];
    },
  });
}

export function useReport(id: string | null) {
  return useQuery({
    queryKey: ["report", id],
    enabled: id != null,
    queryFn: async (): Promise<Report> => {
      const { data, error } = await api.GET("/reports/{id}", { params: { path: { id: id! } } });
      if (error) throw error;
      return data as Report;
    },
  });
}

export function useArtifact(id: string | null) {
  return useQuery({
    queryKey: ["artifact", id],
    enabled: id != null,
    queryFn: async (): Promise<Artifact> => {
      const { data, error } = await api.GET("/artifacts/{id}", { params: { path: { id: id! } } });
      if (error) throw error;
      return data as Artifact;
    },
  });
}
```

`frontend/src/hooks/useSubmit.ts`:
```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Job } from "@/api/types";

function useJobsInvalidator() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["jobs"] });
}

export function useSubmitPack() {
  const invalidate = useJobsInvalidator();
  return useMutation({
    mutationFn: async (form: FormData): Promise<Job> => {
      const { data, error } = await api.POST("/pack", {
        body: form as unknown as never,
        bodySerializer: (b: FormData) => b, // send multipart as-is
      });
      if (error) throw error;
      return data as Job;
    },
    onSuccess: invalidate,
  });
}

function useModelRefSubmit(path: "/detect" | "/scan") {
  const invalidate = useJobsInvalidator();
  return useMutation({
    mutationFn: async (body: { model_ref: string }): Promise<Job> => {
      const { data, error } = await api.POST(path, { body });
      if (error) throw error;
      return data as Job;
    },
    onSuccess: invalidate,
  });
}

export const useSubmitDetect = () => useModelRefSubmit("/detect");
export const useSubmitScan = () => useModelRefSubmit("/scan");
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/hooks/useJob.test.tsx src/hooks/useSubmit.test.tsx && npm run typecheck`
Expected: PASS + typecheck clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/hooks/queryClient.ts frontend/src/hooks/useJob.ts frontend/src/hooks/useSubmit.ts \
        frontend/src/hooks/useJob.test.tsx frontend/src/hooks/useSubmit.test.tsx frontend/src/main.tsx
git commit -m "feat(ui): add TanStack Query provider, job/report/artifact + submit hooks"
```

---

### Task 6: hooks — useJobProgress (WS live + Query polling fallback)

**Files:**
- Create: `frontend/src/hooks/useJobProgress.ts`
- Test: `frontend/src/hooks/useJobProgress.test.tsx`

**Interfaces:**
- Consumes: `createJobProgressSocket` (Task 4), `useJob` (Task 5).
- Produces: `useJobProgress(jobId) -> { event: ProgressView | null, connected: boolean, status?: string }`. While the socket is open it surfaces the latest live `ProgressView`; when the socket is down it derives a `ProgressView` from the polled job row (`progress_step`/`progress_pct`) so the UI still advances (spec §8 R2). `status` comes from the Query job row.

- [ ] **Step 1: Write the failing test**

`frontend/src/hooks/useJobProgress.test.tsx`:
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, expect, test, vi } from "vitest";
import { useJobProgress } from "@/hooks/useJobProgress";

let handlers: { onOpen?: () => void; onEvent: (e: unknown) => void; onClose?: (r: boolean) => void };
const close = vi.fn();
vi.mock("@/lib/ws", () => ({
  createJobProgressSocket: (_id: string, h: typeof handlers) => { handlers = h; return { close }; },
}));
vi.mock("@/hooks/useJob", () => ({
  useJob: () => ({ data: { status: "running", progress_step: "train", progress_pct: 0.2 } }),
}));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);
afterEach(() => vi.clearAllMocks());

test("live WS event wins; on close it falls back to the polled job row", () => {
  const { result } = renderHook(() => useJobProgress("j1"), { wrapper });

  act(() => handlers.onOpen?.());
  act(() => handlers.onEvent({ step: "train", pct: 0.8, detail: "epoch 160" }));
  expect(result.current.connected).toBe(true);
  expect(result.current.event).toEqual({ step: "train", pct: 0.8, detail: "epoch 160" });

  act(() => handlers.onClose?.(true));
  expect(result.current.connected).toBe(false);
  expect(result.current.event).toEqual({ step: "train", pct: 0.2, detail: null }); // from Query
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/hooks/useJobProgress.test.tsx`
Expected: FAIL — hook missing.

- [ ] **Step 3: Implement**

`frontend/src/hooks/useJobProgress.ts`:
```ts
import { useEffect, useState } from "react";
import { createJobProgressSocket } from "@/lib/ws";
import { useJob } from "@/hooks/useJob";
import type { ProgressEvent } from "@/api/types";

export type ProgressView = { step: string; pct: number; detail: string | null };

export type LiveProgress = {
  event: ProgressView | null;
  connected: boolean;
  status?: string;
};

export function useJobProgress(jobId: string): LiveProgress {
  const [live, setLive] = useState<ProgressView | null>(null);
  const [connected, setConnected] = useState(false);

  // Query is the source of truth and drives the polling fallback on reconnect.
  const job = useJob(jobId);

  useEffect(() => {
    if (jobId === "") return;
    const socket = createJobProgressSocket(jobId, {
      onOpen: () => setConnected(true),
      onEvent: (e: ProgressEvent) => setLive({ step: e.step, pct: e.pct, detail: e.detail ?? null }),
      onClose: () => setConnected(false),
    });
    return () => socket.close();
  }, [jobId]);

  const row = job.data as { progress_step?: string; progress_pct?: number; status?: string } | undefined;
  const fallback: ProgressView | null =
    !connected && row ? { step: row.progress_step ?? "", pct: row.progress_pct ?? 0, detail: null } : null;

  return {
    event: connected ? live : (fallback ?? live),
    connected,
    status: row?.status,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/hooks/useJobProgress.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/hooks/useJobProgress.ts frontend/src/hooks/useJobProgress.test.tsx
git commit -m "feat(ui): add useJobProgress with WS live stream + Query polling fallback"
```

---

### Task 7: component — Uploader

**Files:**
- Create: `frontend/src/components/Uploader.tsx`
- Test: `frontend/src/components/Uploader.test.tsx`

**Interfaces:**
- Consumes: nothing (pure presentational).
- Produces: `<Uploader accept label maxBytes? onFile />`. Validates extension (comma-separated `accept`) and optional size; on valid selection calls `onFile(file)` and shows the name; on invalid shows a `role="alert"` message and does not fire `onFile`. Keyboard-focusable native file input with an `aria-label`.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/Uploader.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { Uploader } from "@/components/Uploader";

test("accepts a matching file and calls onFile", async () => {
  const onFile = vi.fn();
  render(<Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />);
  const input = screen.getByLabelText(/repository/i) as HTMLInputElement;
  await userEvent.upload(input, new File(["x"], "repo.zip", { type: "application/zip" }));
  expect(onFile).toHaveBeenCalledOnce();
  expect(screen.getByText("repo.zip")).toBeInTheDocument();
});

test("rejects a wrong extension without firing onFile", async () => {
  const onFile = vi.fn();
  render(<Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />);
  const input = screen.getByLabelText(/repository/i) as HTMLInputElement;
  await userEvent.upload(input, new File(["x"], "notes.txt", { type: "text/plain" }));
  expect(onFile).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toHaveTextContent(/\.zip/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/components/Uploader.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement**

`frontend/src/components/Uploader.tsx`:
```tsx
import { useState } from "react";

export type UploaderProps = {
  accept: string; // e.g. ".zip" or ".safetensors,.pak"
  label: string;
  maxBytes?: number;
  onFile: (file: File) => void;
};

export function Uploader({ accept, label, maxBytes, onFile }: UploaderProps) {
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState<string | null>(null);
  const accepts = accept.split(",").map((s) => s.trim().toLowerCase());

  const validate = (file: File): string | null => {
    if (!accepts.some((a) => file.name.toLowerCase().endsWith(a))) return `Expected ${accept}`;
    if (maxBytes && file.size > maxBytes) return `File exceeds ${maxBytes} bytes`;
    return null;
  };

  const handle = (file: File | undefined) => {
    if (!file) return;
    const err = validate(file);
    if (err) {
      setError(err);
      setName(null);
      return;
    }
    setError(null);
    setName(file.name);
    onFile(file);
  };

  return (
    <div className="rounded-lg border border-dashed p-6">
      <label className="block text-sm font-medium">
        {label}
        <input
          type="file"
          accept={accept}
          aria-label={label}
          className="mt-2 block w-full text-sm"
          onChange={(e) => handle(e.target.files?.[0])}
        />
      </label>
      {name && <p className="mt-2 text-sm text-emerald-700" role="status">{name}</p>}
      {error && <p className="mt-2 text-sm text-red-700" role="alert">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/components/Uploader.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/Uploader.tsx frontend/src/components/Uploader.test.tsx
git commit -m "feat(ui): add presentational Uploader with extension/size validation"
```

---

### Task 8: component — JobProgress

**Files:**
- Create: `frontend/src/components/JobProgress.tsx`
- Test: `frontend/src/components/JobProgress.test.tsx`

**Interfaces:**
- Consumes: nothing (pure presentational; fed by `useJobProgress` at the page).
- Produces: `<JobProgress step pct detail? status? connected />`. Renders an ARIA progressbar clamped to 0–100%, the step/detail lines, and — when `connected=false` — a `data-testid="fallback-indicator"` "polling for updates" note.

- [ ] **Step 1: Write the failing test**

`frontend/src/components/JobProgress.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { JobProgress } from "@/components/JobProgress";

test("renders clamped percent, detail, and connected state", () => {
  render(<JobProgress step="train" pct={0.4} detail="epoch 80/200" status="running" connected />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
  expect(screen.getByText("epoch 80/200")).toBeInTheDocument();
  expect(screen.queryByTestId("fallback-indicator")).not.toBeInTheDocument();
});

test("shows the polling fallback indicator when disconnected", () => {
  render(<JobProgress step="train" pct={0.4} status="running" connected={false} />);
  expect(screen.getByTestId("fallback-indicator")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- src/components/JobProgress.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Implement**

`frontend/src/components/JobProgress.tsx`:
```tsx
export type JobProgressProps = {
  step: string;
  pct: number; // 0..1
  detail?: string | null;
  status?: string;
  connected: boolean;
};

export function JobProgress({ step, pct, detail, status, connected }: JobProgressProps) {
  const clamped = Math.min(Math.max(pct, 0), 1);
  const nowPct = Math.round(clamped * 100);
  const width = `${nowPct}%`;
  return (
    <div className="space-y-2" data-testid="job-progress">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{step || status || "queued"}</span>
        <span>{width}</span>
      </div>
      <div className="h-2 w-full rounded bg-slate-200 dark:bg-slate-700">
        <div
          className="h-2 rounded bg-blue-600 transition-all"
          style={{ width }}
          role="progressbar"
          aria-valuenow={nowPct}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      {detail && <p className="text-xs text-slate-600 dark:text-slate-300">{detail}</p>}
      {!connected && (
        <p className="text-xs text-amber-700" role="status" data-testid="fallback-indicator">
          live stream lost — polling for updates
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- src/components/JobProgress.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/JobProgress.tsx frontend/src/components/JobProgress.test.tsx
git commit -m "feat(ui): add presentational JobProgress bar with fallback indicator"
```

---

### Task 9: components — VerdictBadge + SignalBreakdown (detect surface)

**Files:**
- Create: `frontend/src/lib/report-view.ts`, `frontend/src/components/VerdictBadge.tsx`, `frontend/src/components/SignalBreakdown.tsx`
- Test: `frontend/src/components/VerdictBadge.test.tsx`, `frontend/src/components/SignalBreakdown.test.tsx`

**Interfaces:**
- Consumes: the color scale (Task 3), the generated `Report` type (Task 2).
- Produces:
  - `report-view.ts`: presentational view models over the opaque section payloads — `SignalItem`, `Finding`, `Behavior`, and `sectionsByType(report)` returning `{ signals, findings, behavior }`. (These are the allowed view types over `dict`-shaped section `data`.)
  - `VerdictBadge`: `<VerdictBadge kind label score confidence />` toned by `verdictTone` (detect) or `riskTone` (scan).
  - `SignalBreakdown`: `<SignalBreakdown signals />` — one card per signal with score, confidence, and its evidence key/values.

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/VerdictBadge.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { VerdictBadge } from "@/components/VerdictBadge";

test("detect verdict shows label + score + confidence and a danger tone", () => {
  render(<VerdictBadge kind="detect" label="MEMORIZED-CODE-LIKELY" score={0.91} confidence={0.8} />);
  const badge = screen.getByTestId("verdict-badge");
  expect(badge).toHaveTextContent("MEMORIZED-CODE-LIKELY");
  expect(badge).toHaveTextContent("91%");
  expect(badge).toHaveTextContent("80%");
  expect(badge.className).toContain("red");
});
```

`frontend/src/components/SignalBreakdown.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { SignalBreakdown } from "@/components/SignalBreakdown";

test("renders one card per signal with evidence", () => {
  render(
    <SignalBreakdown
      signals={[
        { name: "spectral", score: 0.9, confidence: 0.7, evidence: { alpha: 2.1, outliers: 5 } },
        { name: "weight_norm", score: 0.4, confidence: 0.5, evidence: {} },
      ]}
    />,
  );
  expect(screen.getByText("spectral")).toBeInTheDocument();
  expect(screen.getByText("weight_norm")).toBeInTheDocument();
  expect(screen.getByText("alpha")).toBeInTheDocument();
  expect(screen.getByText("2.1")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/components/VerdictBadge.test.tsx src/components/SignalBreakdown.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

`frontend/src/lib/report-view.ts`:
```ts
import type { Report } from "@/api/types";

export type SignalItem = { name: string; score: number; confidence: number; evidence: Record<string, unknown> };
export type Finding = { severity: string; rule: string; file: string; line: number | null; note: string };
export type Behavior = {
  syscalls: string[];
  fs_writes: string[];
  blocked_net: string[];
  disagreement?: string | null;
};

type Section = Report["sections"][number];
type Typed = { type?: string; data?: unknown };

export function sectionsByType(report: Report): {
  signals: SignalItem[];
  findings: Finding[];
  behavior: Behavior | null;
} {
  const sections = report.sections as (Section & Typed)[];
  const of = (t: string) => sections.filter((s) => s.type === t);
  const signals = of("signals").flatMap(
    (s) => ((s.data as { signals?: SignalItem[] } | undefined)?.signals ?? []),
  );
  const findings = of("findings").flatMap(
    (s) => ((s.data as { findings?: Finding[] } | undefined)?.findings ?? []),
  );
  const behavior = (of("behavior")[0]?.data as Behavior | undefined) ?? null;
  return { signals, findings, behavior };
}
```

`frontend/src/components/VerdictBadge.tsx`:
```tsx
import { formatPct } from "@/lib/format";
import { riskTone, toneClasses, verdictTone } from "@/lib/verdict";

export type VerdictBadgeProps = {
  kind: "detect" | "scan";
  label: string;
  score: number;
  confidence: number;
};

export function VerdictBadge({ kind, label, score, confidence }: VerdictBadgeProps) {
  const tone = kind === "detect" ? verdictTone(label) : riskTone(label);
  return (
    <div className={`inline-flex flex-col rounded-lg border px-4 py-2 ${toneClasses[tone]}`} data-testid="verdict-badge">
      <span className="text-lg font-semibold">{label}</span>
      <span className="text-xs">score {formatPct(score)} · confidence {formatPct(confidence)}</span>
    </div>
  );
}
```

`frontend/src/components/SignalBreakdown.tsx`:
```tsx
import { formatPct } from "@/lib/format";
import type { SignalItem } from "@/lib/report-view";

export function SignalBreakdown({ signals }: { signals: SignalItem[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="signal-breakdown">
      {signals.map((s) => (
        <div key={s.name} className="rounded-lg border p-3">
          <div className="flex items-center justify-between">
            <span className="font-medium">{s.name}</span>
            <span className="text-sm">{formatPct(s.score)}</span>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300">confidence {formatPct(s.confidence)}</p>
          <dl className="mt-2 space-y-0.5 text-xs">
            {Object.entries(s.evidence).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/components/VerdictBadge.test.tsx src/components/SignalBreakdown.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/lib/report-view.ts frontend/src/components/VerdictBadge.tsx frontend/src/components/SignalBreakdown.tsx \
        frontend/src/components/VerdictBadge.test.tsx frontend/src/components/SignalBreakdown.test.tsx
git commit -m "feat(ui): add VerdictBadge + SignalBreakdown + report section view models"
```

---

### Task 10: components — FindingsTable + BehaviorPanel (scan surface)

**Files:**
- Create: `frontend/src/components/FindingsTable.tsx`, `frontend/src/components/BehaviorPanel.tsx`
- Test: `frontend/src/components/FindingsTable.test.tsx`, `frontend/src/components/BehaviorPanel.test.tsx`

**Interfaces:**
- Consumes: the color scale (Task 3), `Finding`/`Behavior` view models (Task 9).
- Produces:
  - `FindingsTable`: `<FindingsTable findings />` — columns severity/rule/file/line/note; default sort severity-descending; header toggles direction; severity chip toned by `severityTone`.
  - `BehaviorPanel`: `<BehaviorPanel behavior />` — syscalls / fs-writes / blocked-net lists plus a `role="alert"` static/dynamic **disagreement** callout when present (spec §3, ARCHITECTURE §5.5).

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/FindingsTable.test.tsx`:
```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test } from "vitest";
import { FindingsTable } from "@/components/FindingsTable";

const FINDINGS = [
  { severity: "low", rule: "B101", file: "a.py", line: 3, note: "assert" },
  { severity: "high", rule: "B602", file: "b.py", line: 9, note: "shell=True" },
];

test("defaults to severity-descending, toggles on header click", async () => {
  render(<FindingsTable findings={FINDINGS} />);
  const firstRow = () => within(screen.getByTestId("findings-table")).getAllByRole("row")[1];
  expect(firstRow()).toHaveTextContent("high");
  await userEvent.click(screen.getByTestId("sort-severity"));
  expect(firstRow()).toHaveTextContent("low");
});
```

`frontend/src/components/BehaviorPanel.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { BehaviorPanel } from "@/components/BehaviorPanel";

test("renders behavior lists and the disagreement callout", () => {
  render(
    <BehaviorPanel
      behavior={{
        syscalls: ["connect", "execve"],
        fs_writes: ["/tmp/x"],
        blocked_net: ["1.2.3.4:443"],
        disagreement: "static flagged net; dynamic saw none",
      }}
    />,
  );
  expect(screen.getByText("execve")).toBeInTheDocument();
  expect(screen.getByTestId("disagreement")).toHaveTextContent(/static flagged net/);
  expect(screen.getByRole("alert")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/components/FindingsTable.test.tsx src/components/BehaviorPanel.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Implement**

`frontend/src/components/FindingsTable.tsx`:
```tsx
import { useState } from "react";
import type { Finding } from "@/lib/report-view";
import { severityTone, toneClasses } from "@/lib/verdict";

const RANK: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };

export function FindingsTable({ findings }: { findings: Finding[] }) {
  const [desc, setDesc] = useState(true);
  const sorted = [...findings].sort((a, b) => {
    const d = (RANK[b.severity.toLowerCase()] ?? 0) - (RANK[a.severity.toLowerCase()] ?? 0);
    return desc ? d : -d;
  });
  return (
    <table className="w-full text-sm" data-testid="findings-table">
      <thead>
        <tr className="text-left">
          <th>
            <button type="button" onClick={() => setDesc((v) => !v)} data-testid="sort-severity">
              severity {desc ? "▼" : "▲"}
            </button>
          </th>
          <th>rule</th>
          <th>file</th>
          <th>line</th>
          <th>note</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((f, i) => (
          <tr key={`${f.file}:${f.rule}:${i}`} className="border-t">
            <td>
              <span className={`rounded border px-2 ${toneClasses[severityTone(f.severity)]}`}>{f.severity}</span>
            </td>
            <td className="font-mono">{f.rule}</td>
            <td className="font-mono">{f.file}</td>
            <td>{f.line ?? "—"}</td>
            <td>{f.note}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`frontend/src/components/BehaviorPanel.tsx`:
```tsx
import type { Behavior } from "@/lib/report-view";

function BehaviorList({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4 className="text-sm font-medium">{title}</h4>
      {items.length === 0 ? (
        <p className="text-xs text-slate-500">none</p>
      ) : (
        <ul className="list-disc pl-5 text-xs">
          {items.map((it, i) => (
            <li key={i} className="font-mono">{it}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BehaviorPanel({ behavior }: { behavior: Behavior }) {
  return (
    <div className="space-y-3" data-testid="behavior-panel">
      {behavior.disagreement && (
        <div
          className="rounded border border-amber-300 bg-amber-50 p-3 text-sm dark:bg-amber-950"
          role="alert"
          data-testid="disagreement"
        >
          Static/dynamic disagreement: {behavior.disagreement}
        </div>
      )}
      <BehaviorList title="Syscalls" items={behavior.syscalls} />
      <BehaviorList title="Filesystem writes" items={behavior.fs_writes} />
      <BehaviorList title="Blocked network" items={behavior.blocked_net} />
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/components/FindingsTable.test.tsx src/components/BehaviorPanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/FindingsTable.tsx frontend/src/components/BehaviorPanel.tsx \
        frontend/src/components/FindingsTable.test.tsx frontend/src/components/BehaviorPanel.test.tsx
git commit -m "feat(ui): add FindingsTable (severity sort) + BehaviorPanel (disagreement callout)"
```

---

### Task 11: components — ReportView (kind-branch) + PackResultCard (honest metrics)

**Files:**
- Create: `frontend/src/components/ReportView.tsx`, `frontend/src/components/PackResultCard.tsx`
- Test: `frontend/src/components/ReportView.test.tsx`, `frontend/src/components/PackResultCard.test.tsx`

**Interfaces:**
- Consumes: `VerdictBadge`, `SignalBreakdown`, `FindingsTable`, `BehaviorPanel` (Tasks 9–10), `sectionsByType` (Task 9), formatters (Task 3).
- Produces:
  - `ReportView`: `<ReportView report />` — the **single** renderer. Shared: `VerdictBadge` + a `limitations` list. Branch on `report.kind` **only**: `detect` → `SignalBreakdown`; `scan` → `FindingsTable` + `BehaviorPanel`. The detect "signature not proof; cannot recover code" note arrives in `report.limitations` (ADR-007) and is rendered here.
  - `PackResultCard`: `<PackResultCard metrics downloadHref />` — honest side-by-side `original_bytes` / `gzip_bytes` / `artifact_bytes` + `compression_ratio_vs_original`, with a plain-language "not a compressor" line (ADR-003) and a download link.

- [ ] **Step 1: Write the failing tests**

`frontend/src/components/ReportView.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { ReportView } from "@/components/ReportView";
import type { Report } from "@/api/types";

const detect = {
  kind: "detect",
  schema_version: "1.0",
  verdict: { label: "MEMORIZED-CODE-LIKELY", score: 0.9, confidence: 0.8 },
  sections: [{ type: "signals", title: "Signals", data: { signals: [{ name: "spectral", score: 0.9, confidence: 0.7, evidence: {} }] } }],
  evidence: {},
  limitations: ["Signature, not proof: cannot recover code from weights alone."],
} as unknown as Report;

const scan = {
  kind: "scan",
  schema_version: "1.0",
  verdict: { label: "malicious", score: 0.8, confidence: 0.75 },
  sections: [
    { type: "findings", title: "Static", data: { findings: [{ severity: "high", rule: "B602", file: "b.py", line: 9, note: "shell=True" }] } },
    { type: "behavior", title: "Dynamic", data: { syscalls: ["execve"], fs_writes: [], blocked_net: ["1.2.3.4:443"], disagreement: null } },
  ],
  evidence: {},
  limitations: [],
} as unknown as Report;

test("detect report renders signals + verdict + the 'signature not proof' limitation", () => {
  render(<ReportView report={detect} />);
  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
  expect(screen.getByTestId("signal-breakdown")).toBeInTheDocument();
  expect(screen.getByTestId("limitations")).toHaveTextContent(/signature, not proof/i);
  expect(screen.queryByTestId("findings-table")).not.toBeInTheDocument();
});

test("scan report renders findings + behavior, not signals", () => {
  render(<ReportView report={scan} />);
  expect(screen.getByTestId("report-scan")).toBeInTheDocument();
  expect(screen.getByTestId("findings-table")).toBeInTheDocument();
  expect(screen.getByTestId("behavior-panel")).toBeInTheDocument();
  expect(screen.queryByTestId("signal-breakdown")).not.toBeInTheDocument();
});
```

`frontend/src/components/PackResultCard.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { PackResultCard } from "@/components/PackResultCard";

test("shows honest original/gzip/artifact sizes + download link", () => {
  render(
    <PackResultCard
      metrics={{ original_bytes: 180_000, gzip_bytes: 48_000, artifact_bytes: 7_050_000, compression_ratio_vs_original: 39.2 }}
      downloadHref="/api/artifacts/a1?download=1"
    />,
  );
  const card = screen.getByTestId("pack-result");
  expect(card).toHaveTextContent("175.8 KB"); // original
  expect(card).toHaveTextContent("46.9 KB");  // gzip
  expect(card).toHaveTextContent("6.7 MB");   // artifact
  expect(screen.getByTestId("download")).toHaveAttribute("href", "/api/artifacts/a1?download=1");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/components/ReportView.test.tsx src/components/PackResultCard.test.tsx`
Expected: FAIL — components missing.

- [ ] **Step 3: Implement**

`frontend/src/components/ReportView.tsx`:
```tsx
import type { Report } from "@/api/types";
import { sectionsByType } from "@/lib/report-view";
import { BehaviorPanel } from "@/components/BehaviorPanel";
import { FindingsTable } from "@/components/FindingsTable";
import { SignalBreakdown } from "@/components/SignalBreakdown";
import { VerdictBadge } from "@/components/VerdictBadge";

export function ReportView({ report }: { report: Report }) {
  const { signals, findings, behavior } = sectionsByType(report);
  return (
    <div className="space-y-4" data-testid={`report-${report.kind}`}>
      <VerdictBadge
        kind={report.kind}
        label={report.verdict.label}
        score={report.verdict.score}
        confidence={report.verdict.confidence}
      />

      {report.kind === "detect" ? (
        <SignalBreakdown signals={signals} />
      ) : (
        <>
          <FindingsTable findings={findings} />
          {behavior && <BehaviorPanel behavior={behavior} />}
        </>
      )}

      {report.limitations.length > 0 && (
        <section
          className="rounded border border-slate-300 bg-slate-50 p-3 text-sm dark:border-slate-700 dark:bg-slate-800"
          data-testid="limitations"
        >
          <h3 className="font-medium">Limitations</h3>
          <ul className="list-disc pl-5">
            {report.limitations.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
```

`frontend/src/components/PackResultCard.tsx`:
```tsx
import { formatBytes, formatRatio } from "@/lib/format";

export type ArtifactMetrics = {
  original_bytes: number;
  gzip_bytes: number;
  artifact_bytes: number;
  compression_ratio_vs_original: number | null;
};

export function PackResultCard({ metrics, downloadHref }: { metrics: ArtifactMetrics; downloadHref: string }) {
  const rows: [string, string][] = [
    ["Original", formatBytes(metrics.original_bytes)],
    ["gzip", formatBytes(metrics.gzip_bytes)],
    ["Artifact (.pak)", formatBytes(metrics.artifact_bytes)],
  ];
  return (
    <div className="rounded-lg border p-4" data-testid="pack-result">
      <h3 className="font-semibold">Artifact ready</h3>
      <table className="mt-2 w-full text-sm">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-t">
              <td className="py-1">{k}</td>
              <td className="py-1 text-right font-mono">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {metrics.compression_ratio_vs_original != null && (
        <p className="mt-2 text-xs text-slate-600 dark:text-slate-300">
          Artifact is {formatRatio(metrics.compression_ratio_vs_original)} the original — Packer is a
          memorization demo, not a compressor.
        </p>
      )}
      <a href={downloadHref} className="mt-3 inline-block rounded bg-blue-600 px-3 py-1.5 text-white" data-testid="download">
        Download .pak
      </a>
    </div>
  );
}
```
*(`ArtifactMetrics` mirrors the manifest `metrics` block, ARCHITECTURE §5.1; at the page the value comes from the generated `Artifact["metrics"]`.)*

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/components/ReportView.test.tsx src/components/PackResultCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/components/ReportView.tsx frontend/src/components/PackResultCard.tsx \
        frontend/src/components/ReportView.test.tsx frontend/src/components/PackResultCard.test.tsx
git commit -m "feat(ui): add unified ReportView (kind-branch) + honest-metrics PackResultCard"
```

---

### Task 12: pages — Pack + Jobs (composition + router wiring)

**Files:**
- Create: `frontend/src/pages/Pack.tsx`, `frontend/src/pages/Jobs.tsx`, `frontend/src/pages/JobDetail.tsx`
- Modify: `frontend/src/router.tsx` (add `/pack`, `/jobs`, `/jobs/:id`)
- Test: `frontend/src/pages/Pack.test.tsx`, `frontend/src/pages/Jobs.test.tsx`

**Interfaces:**
- Consumes: `useSubmitPack`, `useJobProgress`, `useArtifact`, `useJobs`, `useJob` (Tasks 5–6); `Uploader`, `JobProgress`, `PackResultCard` (Tasks 7–8, 11).
- Produces: the **Pack** screen (drop zip → optional epochs → submit → live `JobProgress` → `PackResultCard` on success) and the **Jobs** list (status filter → row links → `JobDetail` showing progress + result). Pages are composition only; all fetching is in hooks.

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/Pack.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { Pack } from "@/pages/Pack";

const mutate = vi.fn();
vi.mock("@/hooks/useSubmit", () => ({ useSubmitPack: () => ({ mutate, data: { id: "job-1" }, isError: false }) }));
vi.mock("@/hooks/useJobProgress", () => ({
  useJobProgress: () => ({ event: { step: "train", pct: 0.5, detail: "epoch 100" }, connected: true, status: "running" }),
}));
vi.mock("@/hooks/useJob", () => ({ useArtifact: () => ({ data: undefined }) }));

afterEach(() => vi.clearAllMocks());

test("uploading a zip submits a pack job and streams progress", async () => {
  render(<Pack />);
  await userEvent.upload(screen.getByLabelText(/repository/i), new File(["x"], "toy.zip", { type: "application/zip" }));
  expect(mutate).toHaveBeenCalledOnce();
  expect(screen.getByTestId("job-progress")).toHaveTextContent("train");
});
```

`frontend/src/pages/Jobs.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { Jobs } from "@/pages/Jobs";

vi.mock("@/hooks/useJob", () => ({
  useJobs: () => ({ data: [{ id: "abcdef12", type: "detect", status: "succeeded" }] }),
}));

test("lists jobs with links to detail", () => {
  render(<MemoryRouter><Jobs /></MemoryRouter>);
  expect(screen.getByTestId("jobs-table")).toHaveTextContent("detect");
  expect(screen.getByRole("link", { name: /abcdef12/i })).toHaveAttribute("href", "/jobs/abcdef12");
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/pages/Pack.test.tsx src/pages/Jobs.test.tsx`
Expected: FAIL — pages missing.

- [ ] **Step 3: Implement**

`frontend/src/pages/Pack.tsx`:
```tsx
import { useState } from "react";
import { Uploader } from "@/components/Uploader";
import { JobProgress } from "@/components/JobProgress";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useSubmitPack } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useArtifact } from "@/hooks/useJob";

export function Pack() {
  const [epochs, setEpochs] = useState(200);
  const submit = useSubmitPack();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const done = progress.status === "succeeded";
  const artifact = useArtifact(done ? jobId : null);

  const onFile = (file: File) => {
    const form = new FormData();
    form.append("repo", file);
    form.append("epochs", String(epochs));
    submit.mutate(form);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold">Pack a repository</h1>
      <Uploader accept=".zip" label="Repository (.zip)" onFile={onFile} />
      <label className="block text-sm">
        Epochs
        <input
          type="number"
          min={1}
          value={epochs}
          onChange={(e) => setEpochs(Number(e.target.value))}
          className="ml-2 w-24 rounded border px-2"
          data-testid="epochs"
        />
      </label>
      {submit.isError && <p className="text-sm text-red-700" role="alert">Submission failed.</p>}
      {jobId && !done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {done && artifact.data && (
        <PackResultCard
          metrics={artifact.data.metrics as ArtifactMetrics}
          downloadHref={`/api/artifacts/${artifact.data.id}?download=1`}
        />
      )}
    </div>
  );
}
```

`frontend/src/pages/Jobs.tsx`:
```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { useJobs } from "@/hooks/useJob";

const STATUSES = ["", "queued", "running", "succeeded", "failed"];

export function Jobs() {
  const [status, setStatus] = useState("");
  const jobs = useJobs(status ? { status } : {});
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Jobs</h1>
      <select
        value={status}
        onChange={(e) => setStatus(e.target.value)}
        data-testid="status-filter"
        className="rounded border px-2 py-1"
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>{s || "all"}</option>
        ))}
      </select>
      <table className="w-full text-sm" data-testid="jobs-table">
        <thead>
          <tr className="text-left"><th>id</th><th>type</th><th>status</th></tr>
        </thead>
        <tbody>
          {(jobs.data ?? []).map((j) => (
            <tr key={j.id} className="border-t">
              <td><Link to={`/jobs/${j.id}`} className="text-blue-600 underline">{j.id}</Link></td>
              <td>{j.type}</td>
              <td>{j.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

`frontend/src/pages/JobDetail.tsx` (progress + result, routed from the list):
```tsx
import { useParams } from "react-router-dom";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { PackResultCard, type ArtifactMetrics } from "@/components/PackResultCard";
import { useJob, useArtifact, useReport } from "@/hooks/useJob";
import { useJobProgress } from "@/hooks/useJobProgress";

export function JobDetail() {
  const { id = "" } = useParams();
  const job = useJob(id);
  const progress = useJobProgress(id);
  const done = job.data?.status === "succeeded";
  const isPack = job.data?.type === "pack";
  const artifact = useArtifact(done && isPack ? (job.data?.result_ref ?? null) : null);
  const report = useReport(done && !isPack ? (job.data?.result_ref ?? null) : null);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Job {id}</h1>
      {!done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {done && isPack && artifact.data && (
        <PackResultCard metrics={artifact.data.metrics as ArtifactMetrics} downloadHref={`/api/artifacts/${artifact.data.id}?download=1`} />
      )}
      {done && !isPack && report.data && <ReportView report={report.data} />}
    </div>
  );
}
```

`frontend/src/router.tsx` (extend children):
```tsx
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Home } from "@/pages/Home";
import { Pack } from "@/pages/Pack";
import { Jobs } from "@/pages/Jobs";
import { JobDetail } from "@/pages/JobDetail";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "pack", element: <Pack /> },
      { path: "jobs", element: <Jobs /> },
      { path: "jobs/:id", element: <JobDetail /> },
    ],
  },
]);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/pages/Pack.test.tsx src/pages/Jobs.test.tsx && npm run typecheck`
Expected: PASS + typecheck clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/pages/Pack.tsx frontend/src/pages/Jobs.tsx frontend/src/pages/JobDetail.tsx \
        frontend/src/router.tsx frontend/src/pages/Pack.test.tsx frontend/src/pages/Jobs.test.tsx
git commit -m "feat(ui): add Pack + Jobs + JobDetail pages and route wiring"
```

---

### Task 13: pages — Detect + ExtractScan + Report (composition + router wiring)

**Files:**
- Create: `frontend/src/pages/Detect.tsx`, `frontend/src/pages/ExtractScan.tsx`, `frontend/src/pages/Report.tsx`
- Modify: `frontend/src/router.tsx` (add `/detect`, `/scan`, `/reports/:id`)
- Test: `frontend/src/pages/Detect.test.tsx`, `frontend/src/pages/ExtractScan.test.tsx`

**Interfaces:**
- Consumes: `useSubmitDetect`/`useSubmitScan`, `useJobProgress`, `useReport` (Tasks 5–6); `ReportView`, `JobProgress` (Tasks 8, 11).
- Produces: **Detect** (model picker → submit → progress → detect `ReportView`), **ExtractScan** (model picker + optional artifact id → submit → progress → reconstruction banner `byte-exact ✓` | `best-effort` → scan `ReportView`), and a **Report** route that renders any stored report by id.

- [ ] **Step 1: Write the failing tests**

`frontend/src/pages/Detect.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { Detect } from "@/pages/Detect";
import type { Report } from "@/api/types";

const mutate = vi.fn();
vi.mock("@/hooks/useSubmit", () => ({ useSubmitDetect: () => ({ mutate, data: { id: "j1", result_ref: "r1" } }) }));
vi.mock("@/hooks/useJobProgress", () => ({ useJobProgress: () => ({ event: null, connected: true, status: "succeeded" }) }));
vi.mock("@/hooks/useJob", () => ({
  useReport: () => ({
    data: {
      kind: "detect", schema_version: "1.0",
      verdict: { label: "UNLIKELY", score: 0.1, confidence: 0.6 },
      sections: [], evidence: {},
      limitations: ["Signature, not proof."],
    } as unknown as Report,
  }),
}));

afterEach(() => vi.clearAllMocks());

test("submits a model_ref and renders the detect report", async () => {
  render(<Detect />);
  await userEvent.type(screen.getByTestId("model-ref"), "Qwen/Qwen2.5-0.5B");
  await userEvent.click(screen.getByTestId("submit"));
  expect(mutate).toHaveBeenCalledWith({ model_ref: "Qwen/Qwen2.5-0.5B" });
  expect(screen.getByTestId("report-detect")).toBeInTheDocument();
});
```

`frontend/src/pages/ExtractScan.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ExtractScan } from "@/pages/ExtractScan";
import type { Report } from "@/api/types";

vi.mock("@/hooks/useSubmit", () => ({ useSubmitScan: () => ({ mutate: vi.fn(), data: { id: "j2", result_ref: "r2" } }) }));
vi.mock("@/hooks/useJobProgress", () => ({ useJobProgress: () => ({ event: null, connected: true, status: "succeeded" }) }));
vi.mock("@/hooks/useJob", () => ({
  useReport: () => ({
    data: {
      kind: "scan", schema_version: "1.0",
      verdict: { label: "benign", score: 0.1, confidence: 0.7 },
      sections: [{ type: "findings", title: "Static", data: { findings: [] } }],
      evidence: { extraction: { mode: "exact" } }, limitations: [],
    } as unknown as Report,
  }),
}));

afterEach(() => vi.clearAllMocks());

test("renders the byte-exact banner and the scan report", () => {
  render(<ExtractScan />);
  expect(screen.getByTestId("reconstruction")).toHaveTextContent(/byte-exact/i);
  expect(screen.getByTestId("report-scan")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test -- src/pages/Detect.test.tsx src/pages/ExtractScan.test.tsx`
Expected: FAIL — pages missing.

- [ ] **Step 3: Implement**

`frontend/src/pages/Detect.tsx`:
```tsx
import { useState } from "react";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useSubmitDetect } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useReport } from "@/hooks/useJob";

export function Detect() {
  const [modelRef, setModelRef] = useState("");
  const submit = useSubmitDetect();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const done = progress.status === "succeeded";
  const report = useReport(done ? (submit.data?.result_ref ?? null) : null);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Detect memorized code</h1>
      <div className="flex gap-2">
        <input
          value={modelRef}
          onChange={(e) => setModelRef(e.target.value)}
          placeholder="HF id, uploaded id, or artifact id"
          data-testid="model-ref"
          className="flex-1 rounded border px-3 py-2"
        />
        <button
          type="button"
          onClick={() => submit.mutate({ model_ref: modelRef })}
          className="rounded bg-blue-600 px-4 text-white"
          data-testid="submit"
        >
          Detect
        </button>
      </div>
      {jobId && !done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {report.data && <ReportView report={report.data} />}
    </div>
  );
}
```

`frontend/src/pages/ExtractScan.tsx`:
```tsx
import { useState } from "react";
import { JobProgress } from "@/components/JobProgress";
import { ReportView } from "@/components/ReportView";
import { useSubmitScan } from "@/hooks/useSubmit";
import { useJobProgress } from "@/hooks/useJobProgress";
import { useReport } from "@/hooks/useJob";

export function ExtractScan() {
  const [modelRef, setModelRef] = useState("");
  const submit = useSubmitScan();
  const jobId = submit.data?.id ?? null;
  const progress = useJobProgress(jobId ?? "");
  const done = progress.status === "succeeded";
  const report = useReport(done ? (submit.data?.result_ref ?? null) : null);

  const mode = (report.data?.evidence as { extraction?: { mode?: string } } | undefined)?.extraction?.mode;
  const banner =
    mode === "exact" ? "Reconstruction: byte-exact ✓" : mode ? "Reconstruction: best-effort (blind)" : null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Extract + Scan</h1>
      <div className="flex gap-2">
        <input
          value={modelRef}
          onChange={(e) => setModelRef(e.target.value)}
          placeholder="model_ref (add an artifact id for exact mode)"
          data-testid="model-ref"
          className="flex-1 rounded border px-3 py-2"
        />
        <button type="button" onClick={() => submit.mutate({ model_ref: modelRef })}
          className="rounded bg-blue-600 px-4 text-white" data-testid="submit">
          Run
        </button>
      </div>
      {jobId && !done && (
        <JobProgress
          step={progress.event?.step ?? "queued"}
          pct={progress.event?.pct ?? 0}
          detail={progress.event?.detail}
          status={progress.status}
          connected={progress.connected}
        />
      )}
      {banner && <p className="text-sm font-medium" data-testid="reconstruction">{banner}</p>}
      {report.data && <ReportView report={report.data} />}
    </div>
  );
}
```

`frontend/src/pages/Report.tsx`:
```tsx
import { useParams } from "react-router-dom";
import { ReportView } from "@/components/ReportView";
import { useReport } from "@/hooks/useJob";

export function Report() {
  const { id = "" } = useParams();
  const report = useReport(id || null);
  if (!report.data) return <p>Loading report…</p>;
  return <ReportView report={report.data} />;
}
```

`frontend/src/router.tsx` (add the three routes to `children`):
```tsx
import { Detect } from "@/pages/Detect";
import { ExtractScan } from "@/pages/ExtractScan";
import { Report } from "@/pages/Report";
// ...inside children: [ ... ]
      { path: "detect", element: <Detect /> },
      { path: "scan", element: <ExtractScan /> },
      { path: "reports/:id", element: <Report /> },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test -- src/pages/Detect.test.tsx src/pages/ExtractScan.test.tsx && npm run typecheck && npm run test`
Expected: PASS; full unit suite green; typecheck clean.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/pages/Detect.tsx frontend/src/pages/ExtractScan.tsx frontend/src/pages/Report.tsx \
        frontend/src/router.tsx frontend/src/pages/Detect.test.tsx frontend/src/pages/ExtractScan.test.tsx
git commit -m "feat(ui): add Detect + ExtractScan + Report pages and route wiring"
```

---

### Task 14: Playwright E2E — the three happy paths (Phase-6 gate feeders)

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/pack.spec.ts`, `frontend/e2e/detect.spec.ts`, `frontend/e2e/scan.spec.ts`
- Create fixtures: `frontend/e2e/fixtures/toy_repo.zip` (a few tiny text files)
- Modify: `frontend/package.json` (add `"e2e": "playwright test"`)

**Interfaces:**
- Consumes: the whole running stack — API + workers + Redis + Postgres + the built frontend (DEVELOPMENT §5.1 `docker compose -f docker/compose.dev.yml up`). Base URL from `E2E_BASE_URL` (default `http://localhost:5173`).
- Produces: three E2E specs — **pack a tiny repo**, **detect a fixture**, **extract+scan a fixture** — each asserting that progress appears and the report/result renders. These are the exact specs the Phase-6 E2E gate runs (spec §5, SYSTEM-DESIGN §6.4).

- [ ] **Step 1: Write the failing specs**

`frontend/playwright.config.ts`:
```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000, // pack trains a tiny model on CPU
  expect: { timeout: 60_000 },
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173", trace: "on-first-retry" },
  // No webServer: the full stack (API+workers+redis+pg+frontend) is brought up via docker compose (Phase 6).
});
```

`frontend/e2e/pack.spec.ts`:
```ts
import { expect, test } from "@playwright/test";
import path from "node:path";

test("pack a tiny repo → progress streams → artifact card with honest metrics", async ({ page }) => {
  await page.goto("/pack");
  await page.getByLabel(/repository/i).setInputFiles(path.join(__dirname, "fixtures/toy_repo.zip"));
  await expect(page.getByTestId("job-progress")).toBeVisible();
  const card = page.getByTestId("pack-result");
  await expect(card).toBeVisible({ timeout: 180_000 });
  await expect(card).toContainText("Original");
  await expect(card).toContainText("Artifact (.pak)");
  await expect(page.getByTestId("download")).toBeVisible();
});
```

`frontend/e2e/detect.spec.ts`:
```ts
import { expect, test } from "@playwright/test";

test("detect a fixture → progress → detect report with the limitation note", async ({ page }) => {
  await page.goto("/detect");
  await page.getByTestId("model-ref").fill(process.env.E2E_DETECT_REF ?? "fixtures/memorized.pak");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("verdict-badge")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("report-detect")).toBeVisible();
  await expect(page.getByTestId("limitations")).toContainText(/signature/i);
});
```

`frontend/e2e/scan.spec.ts`:
```ts
import { expect, test } from "@playwright/test";

test("extract+scan a fixture → progress → scan report with findings", async ({ page }) => {
  await page.goto("/scan");
  await page.getByTestId("model-ref").fill(process.env.E2E_SCAN_REF ?? "fixtures/malicious.pak");
  await page.getByTestId("submit").click();
  await expect(page.getByTestId("reconstruction")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("report-scan")).toBeVisible();
  await expect(page.getByTestId("findings-table")).toBeVisible();
});
```

- [ ] **Step 2: Run specs to verify they fail**

Bring the stack up (`docker compose -f docker/compose.dev.yml up --build`), then:
Run: `npm run e2e`
Expected: FAIL initially — e.g. a selector/`data-testid` not yet present, a fixture ref the API can't resolve, or the stack not reachable. Diagnose against the running app (not by loosening assertions).

- [ ] **Step 3: Make them pass**

Reconcile page `data-testid`s with the specs (all were added in Tasks 7–13: `job-progress`, `pack-result`, `download`, `verdict-badge`, `report-detect`, `report-scan`, `limitations`, `reconstruction`, `findings-table`, `model-ref`, `submit`). Provide the detect/scan fixture refs the API accepts (a memorized `.pak` and a planted-malicious `.pak` — reuse Phase-1/Phase-3 fixtures via `E2E_DETECT_REF`/`E2E_SCAN_REF`). Keep `toy_repo.zip` tiny so CPU `pack` finishes inside the timeout.

- [ ] **Step 4: Run specs to verify they pass**

Run: `npm run e2e`
Expected: all three PASS against the running stack. Record the invocation (base URL + fixture refs) so Phase 6 can wire the same specs into its E2E job.

- [ ] **Step 5: Commit**
```bash
git add frontend/playwright.config.ts frontend/e2e frontend/package.json
git commit -m "test(ui): add Playwright E2E for pack/detect/scan happy paths"
```

---

## Phase 5 Definition of Done

*(from spec §7 acceptance criteria + §5 testing plan)*

- [ ] A user can drive **Pack**, **Detect**, and **Extract+Scan** entirely from the browser (routes `/pack`, `/detect`, `/scan`, plus `/jobs`, `/jobs/:id`, `/reports/:id`).
- [ ] Job progress streams live via WebSocket (`useJobProgress` → `/ws/jobs/{id}`), with polling fallback on reconnect (`connected=false` → job-row-driven `JobProgress`, Query as source of truth).
- [ ] Detect and Scan reports render through the single `ReportView` (branching on `kind` only) with verdict, confidence, and evidence; the Detect "signature not proof" limitation note is shown.
- [ ] The Pack artifact card shows honest size metrics (original / gzip / artifact) and the ratio-vs-original note.
- [ ] The API client is generated from OpenAPI; `npm run check:api` fails on drift in CI.
- [ ] Components are presentational and unit-tested with fixture props; hooks own all data fetching + the WS subscription.
- [ ] `npm run typecheck` (strict), `npm run lint`, and `npm run test` are green; `npm run build` produces a bundle.
- [ ] Playwright covers the three happy paths against a running stack (`npm run e2e`) — the Phase-6 E2E gate feeders.

## Self-Review Notes

- **Spec coverage** (phase-5 spec): scaffold + routing + dev proxy ✓ (T1); generated OpenAPI client + CI drift check ✓ (T2); `lib/` color scale + formatters + WS client ✓ (T3–T4); TanStack Query hooks + WS progress hook ✓ (T5–T6); presentational components Uploader/JobProgress/VerdictBadge/SignalBreakdown/FindingsTable/BehaviorPanel/ReportView/PackResultCard ✓ (T7–T11); pages Pack/Detect/ExtractScan/Jobs/JobDetail/Report ✓ (T12–T13); Vitest+RTL throughout + Playwright happy paths ✓ (each task + T14); accessibility smoke (ARIA roles on progressbar/alert/status, keyboard-focusable inputs/buttons) folded into component tests.
- **Interfaces produced here and consumed by Phase 6 (E2E):** routes/screens `Pack`, `Detect`, `ExtractScan`, `Jobs`, `Report`; components `Uploader`, `JobProgress`, `VerdictBadge`, `SignalBreakdown`, `FindingsTable`, `BehaviorPanel`, `ReportView`, `PackResultCard`; hooks `useJob`/`useJobs`/`useReport`/`useArtifact`, `useJobProgress`, `useSubmitPack`/`useSubmitDetect`/`useSubmitScan`; `lib/` `createJobProgressSocket` (WS client), generated `api` client, verdict/risk/severity color scale. Stable `data-testid`s (`job-progress`, `pack-result`, `download`, `verdict-badge`, `report-detect`, `report-scan`, `limitations`, `reconstruction`, `findings-table`, `model-ref`, `submit`) are the Phase-6 selectors.
- **Interfaces consumed from Phase 4 (API):** REST `POST /pack /detect /extract /scan`, `GET /jobs /jobs/{id} /artifacts/{id} /reports/{id}`; WS `/ws/jobs/{id}` streaming `ProgressEvent{step,pct,detail}`; the shared `Report{kind,schema_version,verdict{label,score,confidence},sections,evidence,limitations}`; artifact `metrics{original_bytes,gzip_bytes,artifact_bytes,compression_ratio_vs_original}`. All wire types are generated (`schema.d.ts`) and re-exported, never hand-authored.
- **Constraint fidelity:** components hold zero data-fetching (all in hooks); one `ReportView` with a single `kind` branch (verdict + limitations shared); WS-with-polling-fallback is proven in `useJobProgress.test.tsx`; drift is mechanically caught by `check:api`; strict TS + Conventional Commits throughout.
- **Deferred to Phase 6:** the compose file that serves API+workers+frontend behind one origin and the nightly E2E job (this phase writes the specs + config they run; spec §4, §8).
- **Known nuance:** exact generated `["schemas"][...]` key names (e.g. `JobRecord`, `VerdictBlock`, `ArtifactMeta`) depend on the Phase-4 Pydantic model names; Task 2 aligns `api/types.ts` to whatever `schema.d.ts` actually emits rather than inventing shapes. Section payloads (`data`) and `evidence` are opaque dicts on the wire, narrowed only by presentational view models in `lib/report-view.ts` (the sanctioned `dict` carve-out).
