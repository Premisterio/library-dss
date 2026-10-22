import { describe, expect, it } from "vitest"

import { chooseView, orderedValues, pivot, type Chart, type Dimension } from "./charts"
import { fileNameFrom } from "./download"
import { formatMonth, formatValue } from "./format"
import { accessToken, clearSession, isAuthPath, setSession } from "./session"
import { eventData } from "./sse"

function chart(partial: Partial<Chart>): Chart {
  return {
    key: "x",
    dimensions: [],
    measures: [{ key: "loans", unit: "count", window_days: null }],
    attributes: [],
    window_days: null,
    rows: [],
    ...partial,
  }
}

const category: Dimension = { key: "genre", kind: "category", enum: "genre", order: null }
const time: Dimension = { key: "week", kind: "time", enum: null, order: null }
const weekday: Dimension = {
  key: "weekday",
  kind: "category",
  enum: "weekday",
  order: ["mon", "tue", "wed"],
}
const hour: Dimension = { key: "hour", kind: "number", enum: null, order: null }

describe("chooseView", () => {
  it("draws one category dimension as bars", () => {
    const view = chooseView(
      chart({ dimensions: [category], rows: [{ genre: "fantasy", loans: 3 }] })
    )
    expect(view.type).toBe("bars")
  })

  it("draws time as a line of the measures that share the first unit", () => {
    const view = chooseView(
      chart({
        dimensions: [time],
        measures: [
          { key: "searches", unit: "count", window_days: null },
          { key: "share", unit: "ratio", window_days: null },
          { key: "loans", unit: "count", window_days: null },
        ],
        rows: [{ week: "2026-01-05" }, { week: "2026-01-12" }, { week: "2026-01-19" }],
      })
    )
    expect(view).toMatchObject({ type: "line" })
    expect(view.type === "line" && view.measures.map((m) => m.key)).toEqual(["searches", "loans"])
  })

  it("pivots two dimensions with the smaller one across and a ratio measure if any", () => {
    const rows = [0, 1, 2, 3].flatMap((h) =>
      ["mon", "tue", "wed"].map((day) => ({ weekday: day, hour: h, sessions: h, share: 0.1 }))
    )
    const view = chooseView(
      chart({
        dimensions: [weekday, hour],
        measures: [
          { key: "sessions", unit: "count", window_days: null },
          { key: "share", unit: "ratio", window_days: null },
        ],
        rows,
      })
    )
    expect(view).toMatchObject({ type: "heatmap", across: weekday, down: hour })
    expect(view.type === "heatmap" && view.measure.key).toBe("share")
  })

  it("falls back to a table for empty or long charts", () => {
    expect(chooseView(chart({ dimensions: [category] })).type).toBe("table")
    const rows = Array.from({ length: 40 }, (_, i) => ({ genre: `g${i}`, loans: i }))
    expect(chooseView(chart({ dimensions: [category], rows })).type).toBe("table")
  })
})

describe("pivot and order", () => {
  it("follows the dimension's order and finds cells", () => {
    const rows = [
      { weekday: "wed", hour: 0, sessions: 5 },
      { weekday: "mon", hour: 0, sessions: 7 },
    ]
    expect(orderedValues(rows, "weekday", ["mon", "tue", "wed"])).toEqual(["mon", "wed"])
    const table = pivot(chart({ rows }), hour, weekday, {
      key: "sessions",
      unit: "count",
      window_days: null,
    })
    expect(table.across).toEqual(["mon", "wed"])
    expect(table.value(0, "mon")).toBe(7)
    expect(table.value(1, "mon")).toBeNull()
    expect(table.max).toBe(7)
  })
})

describe("formatting", () => {
  it("formats by unit and keeps unknown values visible", () => {
    expect(formatValue(0.0617, "ratio")).toMatch(/^6,2\s?%$/)
    expect(formatValue(169551, "UAH")).toMatch(/^169\s551 грн$/)
    expect(formatValue(45.91, "minutes")).toBe("45,9 хв")
    expect(formatValue(null, "count")).toBe("—")
    expect(formatMonth("2026-09-01")).toMatch(/2026/)
  })
})

describe("file names", () => {
  it("prefers the UTF-8 name and falls back to the plain one", () => {
    const header = `attachment; filename="report-7.pdf"; filename*=UTF-8''%D0%97%D0%B2%D1%96%D1%82%20Q1-2025.pdf`
    expect(fileNameFrom(header, "x")).toBe("Звіт Q1-2025.pdf")
    expect(fileNameFrom('attachment; filename="report-7.pdf"', "x")).toBe("report-7.pdf")
    expect(fileNameFrom(null, "fallback.pdf")).toBe("fallback.pdf")
  })
})

describe("session", () => {
  it("never sends the access token to the auth endpoints", () => {
    expect(isAuthPath("/api/v1/auth/refresh")).toBe(true)
    expect(isAuthPath("/api/v1/auth/login")).toBe(true)
    expect(isAuthPath("/api/v1/auth/me")).toBe(false)
  })

  it("renews the token shortly before it expires", async () => {
    const calls: string[] = []
    const fakeFetch = (async (input: RequestInfo | URL) => {
      calls.push(input instanceof Request ? input.url : input.toString())
      return new Response(JSON.stringify({ access_token: "new", expires_in: 900 }), { status: 200 })
    }) as typeof fetch
    setSession("old", 900, 0)
    await expect(accessToken(1000, fakeFetch)).resolves.toBe("old")
    await expect(accessToken(900_000 - 10_000, fakeFetch)).resolves.toBe("new")
    expect(calls).toEqual(["/api/v1/auth/refresh"])
    clearSession()
    await expect(accessToken(0, fakeFetch)).resolves.toBeNull()
  })
})

describe("event streams", () => {
  it("yields data payloads across chunk boundaries", async () => {
    const chunks = ['data: {"a":1}\n\n: ping\n\nda', 'ta: {"a":2}\r\n\r\n']
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(new TextEncoder().encode(chunk))
        controller.close()
      },
    })
    const seen: string[] = []
    for await (const data of eventData(body)) seen.push(data)
    expect(seen).toEqual(['{"a":1}', '{"a":2}'])
  })
})
