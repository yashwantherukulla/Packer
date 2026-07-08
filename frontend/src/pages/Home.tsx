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
          <Link
            key={c.to}
            to={c.to}
            className="rounded-lg border p-4 hover:bg-slate-50 dark:hover:bg-slate-900"
          >
            <h2 className="font-semibold">{c.title}</h2>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{c.body}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
