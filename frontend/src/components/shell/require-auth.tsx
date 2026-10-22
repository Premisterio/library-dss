import { Navigate, Outlet, useLocation } from "react-router"

import { useAuth } from "@/api/auth"
import { paths } from "@/app/paths"
import { PageSpinner } from "@/components/common/page-spinner"

/** Routes behind sign-in: waits for the silent sign-in, then shows the page or the login form. */
export function RequireAuth() {
  const { ready, signedIn } = useAuth()
  const location = useLocation()
  if (!ready) return <PageSpinner />
  if (!signedIn) return <Navigate to={paths.login} replace state={{ from: location.pathname }} />
  return <Outlet />
}
