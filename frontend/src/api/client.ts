import { createApiClient, type ApiClient } from "@library-dss/api-client"

import { accessToken, clearSession, isAuthPath } from "@/api/session"

function pathOf(url: string): string {
  return new URL(url, window.location.origin).pathname
}

/** A 401 outside the auth endpoints: the session was revoked or the refresh cookie expired. */
function endSessionOn401(path: string, response: Response) {
  if (response.status === 401 && !isAuthPath(path)) clearSession()
}

/** Same-origin client (Vite proxies /api in dev); adds the access token to every call. */
export const api: ApiClient = createApiClient()

api.use({
  async onRequest({ request }) {
    if (isAuthPath(pathOf(request.url))) return request
    const token = await accessToken()
    if (token) request.headers.set("Authorization", `Bearer ${token}`)
    return request
  },
  onResponse({ request, response }) {
    endSessionOn401(pathOf(request.url), response)
    return response
  },
})

/** fetch() with the access token, for streams the typed client cannot read. */
export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken()
  const headers = new Headers(init.headers)
  if (token) headers.set("Authorization", `Bearer ${token}`)
  const response = await fetch(path, { ...init, headers })
  endSessionOn401(path, response)
  return response
}
