import { describe, expect, it } from "vitest"

import { resolveAppearance } from "@/app/appearance"

describe("resolveAppearance", () => {
  it("follows the system unless a choice is made", () => {
    expect(resolveAppearance("system", true)).toBe("dark")
    expect(resolveAppearance("system", false)).toBe("light")
    expect(resolveAppearance("light", true)).toBe("light")
    expect(resolveAppearance("dark", false)).toBe("dark")
  })
})
