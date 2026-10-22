/**
 * Every TanStack Query key. Analytics live outside `datasets`, so refreshing the dataset list
 * never marks the (immutable) analytics stale.
 */
export const keys = {
  me: ["me"] as const,
  enums: ["enums"] as const,
  datasets: ["datasets"] as const,
  datasetList: ["datasets", "list"] as const,
  dataset: (id: number) => ["datasets", "detail", id] as const,
  analytics: (datasetId: number) => ["analytics", datasetId] as const,
  reports: ["reports"] as const,
  reportList: (datasetId: number) => ["reports", "list", datasetId] as const,
  job: (id: string) => ["jobs", id] as const,
}
