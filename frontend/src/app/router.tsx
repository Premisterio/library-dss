import {
  createBrowserRouter,
  isRouteErrorResponse,
  Navigate,
  RouterProvider,
  useRouteError,
} from "react-router"

import { paths } from "@/app/paths"
import type { RouteHandle } from "@/app/route-title"
import { EmptyState } from "@/components/common/empty-state"
import { PageSpinner } from "@/components/common/page-spinner"
import { AppShell } from "@/components/shell/app-shell"
import { RequireAuth } from "@/components/shell/require-auth"
import { Button } from "@/components/ui/button"
import { DatasetsPage } from "@/pages/datasets"
import { LoginPage } from "@/pages/login"
import { NotFound } from "@/pages/not-found"

/** A render error or a failed page load (a stale chunk after a deploy, say). */
function RouteError() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) return <NotFound className="" />
  return (
    <EmptyState
      title="Щось пішло не так"
      description="Сторінку не вдалося показати. Оновіть її; якщо не допоможе, поверніться пізніше."
    >
      <Button onClick={() => window.location.reload()}>Оновити сторінку</Button>
    </EmptyState>
  )
}

const title = (text: string): RouteHandle => ({ title: text })

const router = createBrowserRouter([
  { path: paths.login, element: <LoginPage />, ErrorBoundary: RouteError },
  {
    path: "/",
    element: <RequireAuth />,
    ErrorBoundary: RouteError,
    HydrateFallback: PageSpinner,
    children: [
      { index: true, element: <Navigate to={paths.datasets} replace /> },
      {
        element: <AppShell />,
        // Errors below stay inside the shell, so the navigation keeps working.
        children: [
          {
            path: "datasets",
            element: <DatasetsPage />,
            handle: title("Датасети"),
            ErrorBoundary: RouteError,
          },
          {
            // The dataset pages bring the chart library: they load on first visit.
            path: "d/:datasetId",
            lazy: async () => ({
              Component: (await import("@/pages/dataset-layout")).DatasetLayout,
            }),
            ErrorBoundary: RouteError,
            children: [
              {
                index: true,
                handle: title("Огляд"),
                lazy: async () => ({ Component: (await import("@/pages/overview")).OverviewPage }),
              },
              {
                path: "analytics/:section?",
                handle: title("Аналітика"),
                lazy: async () => ({
                  Component: (await import("@/pages/analytics")).AnalyticsPage,
                }),
              },
              {
                path: "reports",
                handle: title("Звіти"),
                lazy: async () => ({ Component: (await import("@/pages/reports")).ReportsPage }),
              },
              {
                path: "churn",
                handle: title("Відтік"),
                lazy: async () => ({
                  Component: (await import("@/pages/churn-model")).ChurnModelPage,
                }),
              },
              {
                path: "churn/risk",
                handle: title("Відтік"),
                lazy: async () => ({
                  Component: (await import("@/pages/churn-risk")).ChurnRiskPage,
                }),
              },
              {
                path: "churn/plan",
                handle: title("Відтік"),
                lazy: async () => ({
                  Component: (await import("@/pages/churn-plan")).ChurnPlanPage,
                }),
              },
            ],
          },
        ],
      },
    ],
  },
  { path: "*", element: <NotFound /> },
])

export function AppRouter() {
  return <RouterProvider router={router} />
}
