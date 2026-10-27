import {
  keepPreviousData,
  skipToken,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import type { ContentIn } from "@/api/types"

/** The ranking and portfolio under `body`; the last result stays on screen while the next loads. */
export function useContentEvaluation(datasetId: number, body: ContentIn | undefined) {
  return useQuery({
    queryKey: keys.contentEvaluation(datasetId, body),
    queryFn:
      body === undefined
        ? skipToken
        : async () =>
            unwrap(
              await api.POST("/api/v1/datasets/{dataset_id}/content/evaluate", {
                params: { path: { dataset_id: datasetId } },
                body,
              })
            ),
    placeholderData: keepPreviousData,
  })
}

/** Freeze the portfolio as a decision: a report of kind `content`. */
export function useApproveContent(datasetId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ title, decision }: { title: string; decision: ContentIn }) =>
      unwrap(
        await api.POST("/api/v1/datasets/{dataset_id}/content/approve", {
          params: { path: { dataset_id: datasetId } },
          body: { title, decision },
        })
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.reportList(datasetId) }),
  })
}
