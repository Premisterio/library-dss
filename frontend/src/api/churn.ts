import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/api/client"
import { useJob } from "@/api/jobs"
import { keys } from "@/api/keys"
import { expectOk, unwrap } from "@/api/problem"
import type { ChurnRun, Job } from "@/api/types"
import { isTraining } from "@/lib/churn"

const POLL_MS = 2000
export const SCORES_PAGE_SIZE = 50

/** The dataset's churn runs, newest first, refreshed while any of them is training. */
export function useChurnRuns(datasetId: number) {
  return useQuery({
    queryKey: keys.churnRuns(datasetId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/churn-runs", {
          params: { query: { dataset_id: datasetId, limit: 100 } },
        })
      ).items,
    refetchInterval: (query) => (query.state.data?.some(isTraining) ? POLL_MS : false),
  })
}

/** One run with its backtest and explanations, fetched when `enabled` (a trained run). */
export function useChurnRun(runId: number, enabled = true) {
  return useQuery({
    queryKey: keys.churnRun(runId),
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/churn-runs/{run_id}", { params: { path: { run_id: runId } } })),
    enabled,
  })
}

/** Follow a run's training job; every churn query is refreshed once it finishes. */
export function useTrainingJob(run: ChurnRun, onFinished?: (job: Job) => void) {
  const queryClient = useQueryClient()
  return useJob(isTraining(run) ? run.job_id : undefined, (job) => {
    void queryClient.invalidateQueries({ queryKey: keys.churn })
    onFinished?.(job)
  })
}

export function useTrainChurn(datasetId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/v1/datasets/{dataset_id}/churn-runs", {
          params: { path: { dataset_id: datasetId } },
        })
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.churnRuns(datasetId) }),
  })
}

export function useActivateChurnRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (run: ChurnRun) =>
      unwrap(
        await api.POST("/api/v1/churn-runs/{run_id}/activate", {
          params: { path: { run_id: run.id } },
        })
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.churn }),
  })
}

export function useDeleteChurnRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (run: ChurnRun) =>
      expectOk(
        await api.DELETE("/api/v1/churn-runs/{run_id}", { params: { path: { run_id: run.id } } })
      ),
    onSuccess: (_, run) => {
      queryClient.removeQueries({ queryKey: keys.churnRun(run.id) })
      void queryClient.invalidateQueries({ queryKey: keys.churnRuns(run.dataset_id) })
    },
  })
}

/** One page of the members at risk, the riskiest first; a trained run never changes. */
export function useChurnScores(runId: number, offset: number) {
  return useQuery({
    queryKey: keys.churnScores(runId, offset),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/churn-runs/{run_id}/scores", {
          params: { path: { run_id: runId }, query: { limit: SCORES_PAGE_SIZE, offset } },
        })
      ),
    placeholderData: keepPreviousData,
    staleTime: Number.POSITIVE_INFINITY,
  })
}

/** One member at risk with every feature and its typical value. */
export function useChurnScore(runId: number, userId: string | undefined) {
  return useQuery({
    queryKey: keys.churnScore(runId, userId ?? ""),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/churn-runs/{run_id}/scores/{user_id}", {
          params: { path: { run_id: runId, user_id: userId ?? "" } },
        })
      ),
    enabled: userId !== undefined,
    staleTime: Number.POSITIVE_INFINITY,
  })
}
