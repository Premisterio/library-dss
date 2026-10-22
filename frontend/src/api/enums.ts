import { useQuery } from "@tanstack/react-query"
import { useCallback } from "react"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import { labelOf, type LabelFn, type Labels } from "@/lib/labels"

/** Ukrainian labels of every code, from GET /meta/enums (they never change while running). */
export function useEnums() {
  return useQuery({
    queryKey: keys.enums,
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

/** `label(group, code)`: the Ukrainian label, or the code itself while labels load. */
export function useLabel(): LabelFn {
  const { data } = useEnums()
  return useCallback((group, code) => labelOf(data, group, code), [data])
}
