/**
 * The signed-in session. The access token lives only in memory; the refresh token is an
 * httpOnly cookie that the browser sends to /api/v1/auth/* by itself.
 */
import type { TokenOut } from "@/api/types"

type Session = { token: string; expiresAt: number }

const REFRESH_PATH = "/api/v1/auth/refresh"
const EARLY_REFRESH_MS = 30_000 // renew a little before the access token expires

let session: Session | null = null
let refreshing: Promise<string | null> | null = null
const listeners = new Set<() => void>()
const signOutListeners = new Set<() => void>()

function notify() {
  for (const listener of listeners) listener()
}

export function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Called whenever a session ends, whatever ended it: sign-out, a 401, an expired cookie. */
export function onSignOut(listener: () => void): () => void {
  signOutListeners.add(listener)
  return () => signOutListeners.delete(listener)
}

export function isSignedIn(): boolean {
  return session !== null
}

export function setSession(token: string, expiresInSeconds: number, now = Date.now()) {
  session = { token, expiresAt: now + expiresInSeconds * 1000 }
  notify()
}

export function clearSession() {
  if (session === null) return
  session = null
  notify()
  for (const listener of signOutListeners) listener()
}

function isTokenOut(value: unknown): value is Pick<TokenOut, "access_token" | "expires_in"> {
  return (
    typeof value === "object" &&
    value !== null &&
    "access_token" in value &&
    typeof value.access_token === "string" &&
    "expires_in" in value &&
    typeof value.expires_in === "number"
  )
}

/** The current token while it has not expired: a failed renewal does not end a valid session. */
function currentToken(now: number): string | null {
  return session && session.expiresAt > now ? session.token : null
}

/**
 * Exchange the refresh cookie for a new access token, one request at a time. Only a rejected
 * cookie (401/403) ends the session; a network error or a 5xx keeps it for the next attempt.
 */
export function refresh(fetchImpl: typeof fetch = fetch, now = Date.now()): Promise<string | null> {
  refreshing ??= (async () => {
    try {
      const response = await fetchImpl(REFRESH_PATH, { method: "POST", credentials: "same-origin" })
      if (response.status === 401 || response.status === 403) {
        clearSession()
        return null
      }
      if (!response.ok) return currentToken(now)
      const body: unknown = await response.json()
      if (!isTokenOut(body)) {
        clearSession()
        return null
      }
      setSession(body.access_token, body.expires_in)
      return body.access_token
    } catch {
      return currentToken(now)
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

/** A valid access token, renewed first when it is about to expire; null when signed out. */
export async function accessToken(now = Date.now(), fetchImpl: typeof fetch = fetch) {
  if (!session) return null
  if (session.expiresAt - now > EARLY_REFRESH_MS) return session.token
  return refresh(fetchImpl, now)
}

/** Paths that must not carry the access token (refresh would read it as a refresh token). */
export function isAuthPath(path: string): boolean {
  return /\/api\/v1\/auth\/(login|refresh|register)$/.test(path)
}
