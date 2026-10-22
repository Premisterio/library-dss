import { describe, expect, it } from "vitest"

import { formText } from "@/lib/forms"

describe("formText", () => {
  it("trims text fields but can keep them as typed", () => {
    const form = new FormData()
    form.set("email", "  demo@library.ua ")
    form.set("password", " secret ")
    expect(formText(form, "email")).toBe("demo@library.ua")
    expect(formText(form, "password", { trim: false })).toBe(" secret ")
    expect(formText(form, "missing")).toBe("")
  })
})
