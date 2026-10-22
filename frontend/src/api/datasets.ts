import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { api } from "@/api/client"
import { useJob } from "@/api/jobs"
import { keys } from "@/api/keys"
import { expectOk, unwrap } from "@/api/problem"
import type { Dataset, Job, UploadAccepted } from "@/api/types"
import { isFinished, isImporting } from "@/lib/status"

const POLL_MS = 2000

/** The analyst's datasets, refreshed while any of them is importing. */
export function useDatasets() {
  return useQuery({
    queryKey: keys.datasetList,
    queryFn: async () =>
      unwrap(await api.GET("/api/v1/datasets", { params: { query: { limit: 100 } } })).items,
    refetchInterval: (query) => (query.state.data?.some(isImporting) ? POLL_MS : false),
  })
}

/** One dataset, refreshed until its import has finished. */
export function useDataset(id: number) {
  return useQuery({
    queryKey: keys.dataset(id),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/datasets/{dataset_id}", { params: { path: { dataset_id: id } } })
      ),
    refetchInterval: (query) => (isImporting(query.state.data) ? POLL_MS : false),
  })
}

async function uploadDataset({ file, name }: { file: File; name: string }) {
  return unwrap(
    await api.POST("/api/v1/datasets", {
      body: { file: "", name: name || null }, // the serializer below sends the File itself
      bodySerializer: () => {
        const data = new FormData()
        data.append("file", file)
        if (name) data.append("name", name)
        return data
      },
    })
  )
}

/**
 * Upload a file and follow its import job. The upload's error is shown by the form;
 * `onFinished` runs once when the import succeeds or fails.
 */
export function useDatasetImport(onFinished?: (job: Job) => void) {
  const queryClient = useQueryClient()
  const [accepted, setAccepted] = useState<UploadAccepted>()
  const upload = useMutation({
    mutationFn: uploadDataset,
    onMutate: () => setAccepted(undefined),
    onSuccess: (result) => {
      setAccepted(result)
      void queryClient.invalidateQueries({ queryKey: keys.datasets })
    },
    meta: { silent: true },
  })
  const job = useJob(accepted?.job.id, (finished) => {
    void queryClient.invalidateQueries({ queryKey: keys.datasets })
    onFinished?.(finished)
  })
  const following = accepted !== undefined && !isFinished(job.data) && !job.isError
  return {
    upload,
    datasetId: accepted?.dataset.id,
    jobId: accepted?.job.id,
    job: job.data,
    /** Why the job's state could not be read (it is still retried). */
    jobError: job.isError ? job.error : undefined,
    running: upload.isPending || following,
  }
}

export function useDeleteDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (dataset: Dataset) =>
      expectOk(
        await api.DELETE("/api/v1/datasets/{dataset_id}", {
          params: { path: { dataset_id: dataset.id } },
        })
      ),
    onSuccess: (_, dataset) => {
      queryClient.removeQueries({ queryKey: keys.dataset(dataset.id) })
      queryClient.removeQueries({ queryKey: keys.analytics(dataset.id) })
      void queryClient.invalidateQueries({ queryKey: keys.datasets })
      void queryClient.invalidateQueries({ queryKey: keys.reports })
    },
  })
}
