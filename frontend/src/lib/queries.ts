import { useQuery } from "@tanstack/react-query"

import { api, unwrap, type Schemas } from "@/lib/api"

export type Dataset = Schemas["DatasetOut"]
export type Section = Schemas["SectionOut"]
export type SectionKey = Section["key"]
export type Report = Schemas["ReportOut"]
export type Job = Schemas["JobOut"]

/** Analytics sections shown as tabs; the overview has its own page. */
export const ANALYTICS_TABS: SectionKey[] = [
  "usage",
  "content",
  "segments",
  "search",
  "subscriptions",
  "cohorts",
]

export const keys = {
  datasets: ["datasets"] as const,
  dataset: (id: number) => ["datasets", id] as const,
  analytics: (id: number) => ["datasets", id, "analytics"] as const,
  reports: (datasetId: number) => ["reports", datasetId] as const,
}

export function useDatasets() {
  return useQuery({
    queryKey: keys.datasets,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/datasets", { params: { query: { limit: 100 } } })).items,
    // Keep statuses fresh while an import is running anywhere.
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === "pending" || d.status === "importing")
        ? 2000
        : false,
  })
}

export function useDataset(id: number) {
  return useQuery({
    queryKey: keys.dataset(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/datasets/{dataset_id}", { params: { path: { dataset_id: id } } })
      ),
  })
}

/** Every section at once: they are precomputed and small, and every page reuses them. */
export function useAnalytics(id: number, enabled = true) {
  return useQuery({
    queryKey: keys.analytics(id),
    queryFn: async () => {
      const body = unwrap(
        await api.GET("/api/v1/datasets/{dataset_id}/analytics", {
          params: { path: { dataset_id: id } },
        })
      )
      const byKey: Partial<Record<SectionKey, Section>> = {}
      for (const section of body.sections) byKey[section.key] = section
      return byKey
    },
    enabled,
    staleTime: Number.POSITIVE_INFINITY, // a dataset never changes once imported
  })
}

export function useReports(datasetId: number) {
  return useQuery({
    queryKey: keys.reports(datasetId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reports", {
          params: { query: { dataset_id: datasetId, limit: 100 } },
        })
      ).items,
  })
}
