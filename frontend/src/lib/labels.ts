import { EMPTY } from "@/lib/format"

/** Labels of every enum group, by code: GET /meta/enums reshaped for lookups. */
export type Labels = Record<string, Record<string, string>>

/**
 * `label(group, code)`: the Ukrainian label of a code. Groups are strings because the API
 * names some of them itself (a dimension's `enum`).
 */
export type LabelFn = (group: string, code: unknown) => string

export function labelOf(labels: Labels | undefined, group: string, code: unknown): string {
  const text =
    typeof code === "string" || typeof code === "number" || typeof code === "boolean"
      ? String(code)
      : EMPTY
  return labels?.[group]?.[text] ?? text
}
