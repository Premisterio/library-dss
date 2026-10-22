import { createApiClient } from "@library-dss/api-client"
import { describe, expect, it } from "vitest"

import { ApiProblem, errorMessage, expectOk, unwrap } from "@/api/problem"

function thrown(action: () => unknown): unknown {
  try {
    action()
  } catch (error) {
    return error
  }
  throw new Error("expected the action to throw")
}

function clientAnswering(status: number, body: string, contentType: string) {
  return createApiClient({
    baseUrl: "http://test",
    fetch: async () => new Response(body, { status, headers: { "content-type": contentType } }),
  })
}

describe("unwrap", () => {
  it("returns the data of a successful call", async () => {
    const client = clientAnswering(200, '{"status":"ok","version":"2.0.0"}', "application/json")
    expect(unwrap(await client.GET("/api/v1/health"))).toEqual({ status: "ok", version: "2.0.0" })
  })

  it("throws the Problem Details of an error with its code", async () => {
    const problem = { title: "Not Found", status: 404, code: "dataset.not_found", errors: [] }
    const client = clientAnswering(404, JSON.stringify(problem), "application/problem+json")
    const result = await client.GET("/api/v1/health")
    expect(() => expectOk(result)).toThrow(ApiProblem)
    const error = thrown(() => unwrap(result))
    expect(error).toBeInstanceOf(ApiProblem)
    expect(errorMessage(error)).toBe("Датасет не знайдено.")
  })

  it("gives a non-API error page a code from its status", async () => {
    const client = clientAnswering(502, "<html>Bad Gateway</html>", "text/html")
    const result = await client.GET("/api/v1/health")
    const error = thrown(() => unwrap(result))
    expect(error).toMatchObject({ problem: { code: "http.502", status: 502 } })
    expect(errorMessage(error)).toMatch(/^Помилка сервера/)
  })
})

describe("errorMessage", () => {
  it("explains a lost connection", () => {
    expect(errorMessage(new TypeError("Failed to fetch"))).toBe("Немає зв'язку з сервером.")
  })
})
