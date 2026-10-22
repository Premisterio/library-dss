import { describe, expect, it } from "vitest"

import { fileNameFrom } from "@/lib/content-disposition"

describe("fileNameFrom", () => {
  it("prefers the UTF-8 name and falls back to the plain one", () => {
    const header = `attachment; filename="report-7.pdf"; filename*=UTF-8''%D0%97%D0%B2%D1%96%D1%82%20Q1-2025.pdf`
    expect(fileNameFrom(header, "x")).toBe("Звіт Q1-2025.pdf")
    expect(fileNameFrom('attachment; filename="report-7.pdf"', "x")).toBe("report-7.pdf")
    expect(fileNameFrom("attachment; filename*=UTF-8''%E0%A4%A", "x")).toBe("x")
    expect(fileNameFrom(null, "fallback.pdf")).toBe("fallback.pdf")
  })
})
