import { createBrowserRouter } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AddVideoPage } from "./pages/AddVideoPage";
import { JobMonitorPage } from "./pages/JobMonitorPage";
import { JobHistoryPage } from "./pages/JobHistoryPage";
import { WorkspaceListPage } from "./pages/WorkspaceListPage";
import { WorkspaceDetailPage } from "./pages/WorkspaceDetailPage";
import { SettingsPage } from "./pages/SettingsPage";

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <AddVideoPage /> },
      { path: "/jobs", element: <JobHistoryPage /> },
      { path: "/jobs/:jobId", element: <JobMonitorPage /> },
      { path: "/workspaces", element: <WorkspaceListPage /> },
      { path: "/workspaces/:id", element: <WorkspaceDetailPage /> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
]);
