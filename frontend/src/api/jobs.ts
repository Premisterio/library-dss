import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useEffectEvent, useRef, useState } from "react"

import { api, authorizedFetch } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import { eventData } from "@/api/sse"
import type { Job } from "@/api/types"
import { isFinished } from "@/lib/status"

const POLL_MS = 1500
const RECONNECT_MS = 1000

function isJob(value: unknown): value is Job {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "status" in value &&
    typeof value.status === "string" &&
    "progress" in value &&
    typeof value.progress === "number"
  )
}

function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener("abort", () => clearTimeout(timer), { once: true })
  })
}

/**
 * Stream a job's events into the query cache until it finishes. Resolves when the stream
 * cannot be used (an error, a refused request); polling covers the job from then on.
 */
async function streamJob(id: string, signal: AbortSignal, onJob: (job: Job) => void) {
  for (;;) {
    // oxlint-disable-next-line no-await-in-loop -- one connection after another
    const response = await authorizedFetch(`/api/v1/jobs/${id}/events`, { signal })
    if (!response.ok || !response.body) return
    // oxlint-disable-next-line no-await-in-loop -- events arrive one after another
    for await (const data of eventData(response.body)) {
      const job: unknown = JSON.parse(data)
      if (!isJob(job)) continue
      onJob(job)
      if (isFinished(job)) return
    }
    // The server ended the stream early (a restart, a proxy timeout): connect again.
    // oxlint-disable-next-line no-await-in-loop -- reconnect after a pause
    await delay(RECONNECT_MS, signal)
    if (signal.aborted) return
  }
}

/**
 * Follow a job: live over SSE, polled while the stream is down. Polling keeps going through
 * errors, so a restarting API does not leave the job unfollowed. `onFinished` runs once per job.
 */
export function useJob(jobId: string | undefined, onFinished?: (job: Job) => void) {
  const queryClient = useQueryClient()
  const [streamEnded, setStreamEnded] = useState<string>() // the job whose stream is gone

  useEffect(() => {
    if (!jobId) return undefined
    const abort = new AbortController()
    streamJob(jobId, abort.signal, (job) => queryClient.setQueryData(keys.job(jobId), job))
      .catch(() => undefined)
      .finally(() => {
        if (!abort.signal.aborted) setStreamEnded(jobId)
      })
    return () => abort.abort()
  }, [jobId, queryClient])

  const query = useQuery({
    queryKey: keys.job(jobId ?? ""),
    queryFn: async ({ signal }) =>
      unwrap(
        await api.GET("/api/v1/jobs/{job_id}", {
          params: { path: { job_id: jobId ?? "" } },
          signal,
        })
      ),
    enabled: jobId !== undefined,
    refetchInterval: (q) => (isFinished(q.state.data) || streamEnded !== jobId ? false : POLL_MS),
  })

  const reported = useRef<string>(undefined)
  const finished = useEffectEvent((job: Job) => onFinished?.(job))
  const job = query.data
  useEffect(() => {
    if (!jobId || !job || !isFinished(job) || reported.current === jobId) return
    reported.current = jobId
    finished(job)
  }, [jobId, job])

  return query
}
