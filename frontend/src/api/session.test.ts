import { afterEach, describe, expect, it } from "vitest"

import {
  accessToken,
  clearSession,
  isAuthPath,
  isSignedIn,
  onSignOut,
  setSession,
} from "@/api/session"

const MINUTE = 60_000

function fakeFetch(answer: () => Response | Promise<Response>) {
  const calls: string[] = []
  const impl = (async (input: RequestInfo | URL) => {
    calls.push(input instanceof Request ? input.url : input.toString())
    return answer()
  }) as typeof fetch
  return { impl, calls }
}

const tokens = () =>
  new Response(JSON.stringify({ access_token: "new", expires_in: 900 }), { status: 200 })

afterEach(() => clearSession())

describe("session", () => {
  it("never sends the access token to the auth endpoints", () => {
    expect(isAuthPath("/api/v1/auth/refresh")).toBe(true)
    expect(isAuthPath("/api/v1/auth/login")).toBe(true)
    expect(isAuthPath("/api/v1/auth/me")).toBe(false)
  })

  it("renews the token shortly before it expires", async () => {
    const { impl, calls } = fakeFetch(tokens)
    setSession("old", 900, 0)
    await expect(accessToken(MINUTE, impl)).resolves.toBe("old")
    await expect(accessToken(15 * MINUTE - 10_000, impl)).resolves.toBe("new")
    expect(calls).toEqual(["/api/v1/auth/refresh"])
    clearSession()
    await expect(accessToken(0, impl)).resolves.toBeNull()
  })

  it("asks for one renewal when many calls need it at once", async () => {
    const { impl, calls } = fakeFetch(tokens)
    setSession("old", 10, 0)
    const all = await Promise.all([1, 2, 3].map(() => accessToken(5_000, impl)))
    expect(all).toEqual(["new", "new", "new"])
    expect(calls).toHaveLength(1)
  })

  it("keeps a valid session when the renewal fails for a passing reason", async () => {
    setSession("old", 900, 0)
    const now = 15 * MINUTE - 10_000
    const unavailable = fakeFetch(() => new Response("{}", { status: 503 }))
    await expect(accessToken(now, unavailable.impl)).resolves.toBe("old")
    const offline = fakeFetch(() => Promise.reject(new TypeError("Failed to fetch")))
    await expect(accessToken(now, offline.impl)).resolves.toBe("old")
    expect(isSignedIn()).toBe(true)
  })

  it("ends the session when the cookie is rejected, and says so once", async () => {
    let endings = 0
    const stop = onSignOut(() => endings++)
    setSession("old", 10, 0)
    const rejected = fakeFetch(() => new Response("{}", { status: 401 }))
    await expect(accessToken(5_000, rejected.impl)).resolves.toBeNull()
    expect(isSignedIn()).toBe(false)
    clearSession()
    expect(endings).toBe(1)
    stop()
  })
})
