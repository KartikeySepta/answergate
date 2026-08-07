import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './components/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { NewResearchPage } from './pages/NewResearchPage';
import { ProcessingPage } from './pages/ProcessingPage';
import { ProcessingCentrePage } from './pages/ProcessingCentrePage';
import { WorkspaceDetailPage } from './pages/WorkspaceDetailPage';
import { WorkspaceListPage } from './pages/WorkspaceListPage';
import { SettingsPage } from './pages/SettingsPage';

export const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/research', element: <WorkspaceListPage /> },
      { path: '/research/new', element: <NewResearchPage /> },
      { path: '/research/:id', element: <WorkspaceDetailPage /> },
      { path: '/processing', element: <ProcessingCentrePage /> },
      { path: '/processing/:jobId', element: <ProcessingPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
]);
