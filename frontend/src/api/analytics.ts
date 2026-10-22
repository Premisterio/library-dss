import { useQuery } from "@tanstack/react-query"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import type { Sections } from "@/api/types"

/** Every section at once: they are precomputed and small, and every page reuses them. */
export function useAnalytics(datasetId: number) {
  return useQuery({
    queryKey: keys.analytics(datasetId),
    queryFn: async (): Promise<Sections> => {
      const body = unwrap(
        await api.GET("/api/v1/datasets/{dataset_id}/analytics", {
          params: { path: { dataset_id: datasetId } },
        })
      )
      return Object.fromEntries(body.sections.map((section) => [section.key, section]))
    },
    staleTime: Number.POSITIVE_INFINITY, // a dataset never changes once imported
  })
}
