import createClient from "openapi-fetch";
import type { paths } from "./schema";

// baseUrl "/api" pairs with the Vite proxy rewrite so generated paths ("/jobs/{job_id}")
// resolve to /api/jobs/{job_id} in the browser and /jobs/{job_id} at the FastAPI service.
export const api = createClient<paths>({ baseUrl: "/api" });
