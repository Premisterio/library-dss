import { describe, expect, it } from "vitest"

import type { LabelFn } from "@/lib/labels"
import { stageText } from "@/lib/status"

const LABELS: Record<string, Record<string, string>> = {
  job_stage: { load: "Запис у базу", parse: "Розбір файлу" },
  dataset_table: { loans: "Позичення" },
}
const label: LabelFn = (group, code) => LABELS[group]?.[String(code)] ?? String(code)

describe("stageText", () => {
  it("names the stage and the table being loaded", () => {
    expect(stageText("load:loans", label)).toBe("Запис у базу: позичення")
    expect(stageText("parse", label)).toBe("Розбір файлу")
    expect(stageText(null, label)).toBe("У черзі")
  })
})
