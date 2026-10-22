import { describe, expect, it } from "vitest"

import { messageFor } from "@/lib/messages"

describe("messageFor", () => {
  it("knows the API's codes", () => {
    expect(messageFor("auth.invalid_credentials")).toBe("Неправильний e-mail або пароль.")
    expect(messageFor("server.error", null, 500)).toMatch(/^Помилка сервера/)
  })

  it("never shows a raw code for a server error or a non-API answer", () => {
    expect(messageFor("something.new", "Detail", 503)).toMatch(/^Помилка сервера/)
    expect(messageFor("http.502", null, 502)).toMatch(/^Помилка сервера/)
    expect(messageFor("http.404", null, 404)).toBe("Запит не вдався (HTTP 404).")
  })

  it("falls back to the API's detail for an unknown 4xx code", () => {
    expect(messageFor("something.new", "Detail", 409)).toBe("Detail")
  })
})
