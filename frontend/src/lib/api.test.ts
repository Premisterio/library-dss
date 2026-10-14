import { createApiClient } from "@library-dss/api-client"
import { describe, expect, it } from "vitest"

import { fetchHealth } from "./api"

function clientReturning(status: number, body: unknown, contentType = "application/json") {
  const requests: string[] = []
  const client = createApiClient({
    baseUrl: "http://test",
    fetch: async (request: Request) => {
      requests.push(new URL(request.url).pathname)
      return new Response(JSON.stringify(body), {
        status,
        headers: { "content-type": contentType },
      })
    },
  })
  return { client, requests }
}

describe("fetchHealth", () => {
  it("calls the versioned health endpoint", async () => {
    const { client, requests } = clientReturning(200, { status: "ok", version: "2.0.0" })
    await expect(fetchHealth(client)).resolves.toEqual({ status: "ok", version: "2.0.0" })
    expect(requests).toEqual(["/api/v1/health"])
  })

  it("surfaces the Problem Details code on errors", async () => {
    const problem = { title: "Service Unavailable", status: 503, code: "system.down", errors: [] }
    const { client } = clientReturning(503, problem, "application/problem+json")
    await expect(fetchHealth(client)).rejects.toThrow("system.down")
  })
})
