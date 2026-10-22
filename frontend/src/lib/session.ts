/**
 * The signed-in session. The access token lives only in memory; the refresh token is an
 * httpOnly cookie that the browser sends to /api/v1/auth/* by itself.
 */

type Session = { token: string; expiresAt: number }

const REFRESH_PATH = "/api/v1/auth/refresh"
const EARLY_REFRESH_MS = 30_000 // renew a little before the access token expires

let session: Session | null = null
let refreshing: Promise<string | null> | null = null
const listeners = new Set<() => void>()

function notify() {
  for (const listener of listeners) listener()
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function isSignedIn(): boolean {
  return session !== null
}

export function setSession(token: string, expiresInSeconds: number, now = Date.now()) {
  session = { token, expiresAt: now + expiresInSeconds * 1000 }
  notify()
}

export function clearSession() {
  session = null
  notify()
}

type TokenOut = { access_token: string; expires_in: number }

function isTokenOut(value: unknown): value is TokenOut {
  return (
    typeof value === "object" &&
    value !== null &&
    "access_token" in value &&
    typeof value.access_token === "string" &&
    "expires_in" in value &&
    typeof value.expires_in === "number"
  )
}

/** Exchange the refresh cookie for a new access token (one request at a time). */
export function refresh(fetchImpl: typeof fetch = fetch): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const response = await fetchImpl(REFRESH_PATH, { method: "POST", credentials: "same-origin" })
      if (!response.ok) {
        clearSession()
        return null
      }
      const body: unknown = await response.json()
      if (!isTokenOut(body)) {
        clearSession()
        return null
      }
      setSession(body.access_token, body.expires_in)
      return body.access_token
    } catch {
      clearSession()
      return null
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** A valid access token, renewed first when it is about to expire; null when signed out. */
export async function accessToken(now = Date.now(), fetchImpl: typeof fetch = fetch) {
  if (session && session.expiresAt - now > EARLY_REFRESH_MS) return session.token
  if (!session) return null
  return refresh(fetchImpl)
}

/** Paths that must not carry the access token (refresh would read it as a refresh token). */
export function isAuthPath(path: string): boolean {
  return /\/api\/v1\/auth\/(login|refresh|register)$/.test(path)
}
