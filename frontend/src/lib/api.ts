import { createApiClient, type ApiClient, type Schemas } from "@library-dss/api-client"

import { accessToken, clearSession, isAuthPath } from "@/lib/session"

export type { Schemas }
export type Health = Schemas["HealthOut"]
export type Problem = Schemas["Problem"]

/** Same-origin client (Vite proxies /api in dev); adds the access token to every call. */
export const api: ApiClient = createApiClient()

api.use({
  async onRequest({ request }) {
    if (isAuthPath(new URL(request.url, window.location.origin).pathname)) return request
    const token = await accessToken()
    if (token) request.headers.set("Authorization", `Bearer ${token}`)
    return request
  },
  onResponse({ request, response }) {
    // The session was revoked (signed out elsewhere) or the refresh cookie expired.
    const path = new URL(request.url, window.location.origin).pathname
    if (response.status === 401 && !isAuthPath(path)) clearSession()
    return response
  },
})

/** fetch() with the access token, for streams and file downloads. */
export async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken()
  const headers = new Headers(init.headers)
  if (token) headers.set("Authorization", `Bearer ${token}`)
  const response = await fetch(path, { ...init, headers })
  if (response.status === 401) clearSession()
  return response
}

export class ApiProblem extends Error {
  readonly problem: Problem

  constructor(problem: Problem) {
    super(problem.detail ?? problem.code)
    this.problem = problem
  }
}

/** Unwrap an openapi-fetch result: the data, or an ApiProblem with the stable code. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw new ApiProblem(asProblem(result.error, result.response))
  }
  return result.data
}

/** For calls without a body (204): throws an ApiProblem unless the response is ok. */
export function expectOk(result: { error?: unknown; response: Response }): void {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiProblem(asProblem(result.error, result.response))
  }
}

function isProblem(value: unknown): value is Problem {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof value.code === "string" &&
    "status" in value &&
    "title" in value
  )
}

function asProblem(error: unknown, response: Response): Problem {
  if (isProblem(error)) return error
  return {
    type: "about:blank",
    title: response.statusText || "Error",
    status: response.status,
    detail: null,
    code: `http.${response.status}`,
    errors: [],
  }
}

export async function fetchHealth(client: ApiClient = api): Promise<Health> {
  const result = await client.GET("/api/v1/health")
  return unwrap(result)
}
