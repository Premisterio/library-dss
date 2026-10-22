import { createBrowserRouter, Link, Navigate, Outlet, RouterProvider } from "react-router"

import { AppShell } from "@/components/app-shell"
import { Button } from "@/components/ui/button"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { DatasetsPage } from "@/pages/datasets"
import { LoginPage, RequireAuth } from "@/pages/login"

function NotFound() {
  return (
    <Empty className="min-h-svh">
      <EmptyHeader>
        <EmptyTitle>Сторінку не знайдено</EmptyTitle>
        <EmptyDescription>Можливо, посилання застаріло.</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button asChild>
          <Link to="/datasets">До датасетів</Link>
        </Button>
      </EmptyContent>
    </Empty>
  )
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <Outlet />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/datasets" replace /> },
      {
        element: <AppShell />,
        children: [
          { path: "datasets", element: <DatasetsPage /> },
          // Charts (recharts) load only with the dataset pages.
          {
            path: "d/:datasetId",
            lazy: async () => ({ Component: (await import("@/pages/dataset-pages")).OverviewPage }),
          },
          {
            path: "d/:datasetId/analytics/:section?",
            lazy: async () => ({
              Component: (await import("@/pages/dataset-pages")).AnalyticsPage,
            }),
          },
          {
            path: "d/:datasetId/reports",
            lazy: async () => ({ Component: (await import("@/pages/dataset-pages")).ReportsPage }),
          },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
])

export function App() {
  return <RouterProvider router={router} />
}
