import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Home } from "@/pages/Home";
import { Pack } from "@/pages/Pack";
import { Jobs } from "@/pages/Jobs";
import { JobDetail } from "@/pages/JobDetail";
import { Detect } from "@/pages/Detect";
import { ExtractScan } from "@/pages/ExtractScan";
import { Report } from "@/pages/Report";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <Home /> },
      { path: "pack", element: <Pack /> },
      { path: "jobs", element: <Jobs /> },
      { path: "jobs/:id", element: <JobDetail /> },
      { path: "detect", element: <Detect /> },
      { path: "scan", element: <ExtractScan /> },
      { path: "reports/:id", element: <Report /> },
    ],
  },
]);
