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
          <option key={s} value={s}>
            {s || "all"}
          </option>
        ))}
      </select>
      <table className="w-full text-sm" data-testid="jobs-table">
        <thead>
          <tr className="text-left">
            <th>id</th>
            <th>type</th>
            <th>status</th>
          </tr>
        </thead>
        <tbody>
          {(jobs.data ?? []).map((j) => (
            <tr key={j.id} className="border-t">
              <td>
                <Link to={`/jobs/${j.id}`} className="text-blue-600 underline">
                  {j.id}
                </Link>
              </td>
              <td>{j.type}</td>
              <td>{j.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
