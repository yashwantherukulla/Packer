import { afterEach, beforeEach, expect, test, vi } from "vitest";

// openapi-fetch 0.13 captures globalThis.fetch/Request at createClient() time and
// hands `fetch` a Request object (not a URL string); undici's Request also rejects
// the relative "/api" base outside a browser. Resolve path-absolute URLs against a
// dummy origin so the browser-correct relative client is exercisable under Node.
const RealRequest = globalThis.Request;
class TestRequest extends RealRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    super(typeof input === "string" && input.startsWith("/") ? `http://localhost${input}` : input, init);
  }
}

beforeEach(() => vi.resetModules());
afterEach(() => vi.unstubAllGlobals());

test("client issues typed GET /jobs/{job_id} against the /api base and parses JSON", async () => {
  const fetchMock = vi.fn(
    async (..._args: unknown[]) =>
      new Response(JSON.stringify({ id: "j1", type: "detect", status: "succeeded" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("Request", TestRequest);

  // Import after stubbing so createClient() captures the mocked globals.
  const { api } = await import("@/api/client");

  const { data, error } = await api.GET("/jobs/{job_id}", { params: { path: { job_id: "j1" } } });

  expect(error).toBeUndefined();
  expect(data?.status).toBe("succeeded");
  const calledWith = fetchMock.mock.calls[0]?.[0];
  const calledUrl = typeof calledWith === "string" ? calledWith : (calledWith as Request).url;
  expect(calledUrl).toContain("/api/jobs/j1");
});
