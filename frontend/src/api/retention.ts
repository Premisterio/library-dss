import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import type { ChurnRun, PlanIn } from "@/api/types"

/** The best plan for the run's members at risk under `plan`; nothing until a plan is given. */
export function useRetentionPlan(runId: number, plan: PlanIn | undefined) {
  return useQuery({
    queryKey: keys.retentionPlan(runId, plan),
    queryFn:
      plan === undefined
        ? skipToken
        : async () =>
            unwrap(
              await api.POST("/api/v1/churn-runs/{run_id}/plan", {
                params: { path: { run_id: runId } },
                body: plan,
              })
            ),
  })
}

/** Freeze the plan as a decision: a report of kind `retention`. */
export function useApprovePlan(run: ChurnRun) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ title, plan }: { title: string; plan: PlanIn }) =>
      unwrap(
        await api.POST("/api/v1/churn-runs/{run_id}/plan/approve", {
          params: { path: { run_id: run.id } },
          body: { title, plan },
        })
      ),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: keys.reportList(run.dataset_id) }),
  })
}
