import type { ContentIn, PlanIn } from "@/api/types"

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
  churn: ["churn"] as const,
  churnRuns: (datasetId: number) => ["churn", "runs", datasetId] as const,
  activeChurnRun: (datasetId: number) => ["churn", "active", datasetId] as const,
  churnRun: (id: number) => ["churn", "run", id] as const,
  churnScores: (runId: number, offset: number) => ["churn", "scores", runId, offset] as const,
  churnScore: (runId: number, userId: string) => ["churn", "score", runId, userId] as const,
  retentionPlan: (runId: number, plan: PlanIn | undefined) =>
    ["churn", "plan", runId, plan] as const,
  contentEvaluation: (datasetId: number, body: ContentIn | undefined) =>
    ["content", datasetId, body] as const,
}
