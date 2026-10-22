import { useQuery } from "@tanstack/react-query"
import { useCallback } from "react"

import { api, unwrap } from "@/lib/api"

export type Labels = Record<string, Record<string, string>>

/** Ukrainian labels of every code, from GET /meta/enums (they never change while running). */
export function useEnums() {
  return useQuery({
    queryKey: ["enums"],
    queryFn: async (): Promise<Labels> => {
      const body = unwrap(await api.GET("/api/v1/meta/enums"))
      return Object.fromEntries(
        Object.entries(body.enums).map(([group, items]) => [
          group,
          Object.fromEntries(items.map((item) => [item.code, item.label])),
        ])
      )
    },
    staleTime: Number.POSITIVE_INFINITY,
  })
}

export function labelOf(labels: Labels | undefined, group: string, code: unknown): string {
  const text =
    typeof code === "string" || typeof code === "number" || typeof code === "boolean"
      ? String(code)
      : "—"
  return labels?.[group]?.[text] ?? text
}

/** `label(group, code)`: the Ukrainian label, or the code itself while labels load. */
export function useLabel() {
  const { data } = useEnums()
  return useCallback((group: string, code: unknown) => labelOf(data, group, code), [data])
}
