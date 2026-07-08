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
