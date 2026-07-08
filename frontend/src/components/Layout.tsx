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
          <NavLink to="/" className="font-bold">
            Packer
          </NavLink>
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) => (isActive ? "font-medium underline" : "text-slate-500")}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children ?? <Outlet />}</main>
    </div>
  );
}
