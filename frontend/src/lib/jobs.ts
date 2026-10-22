import { useEffect, useState } from "react"

import { api, authorizedFetch, unwrap } from "@/lib/api"
import type { Job } from "@/lib/queries"
import { eventData } from "@/lib/sse"

const TERMINAL = new Set(["succeeded", "failed"])

function isJob(value: unknown): value is Job {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    "status" in value &&
    "progress" in value
  )
}

export function isFinished(job: Job | undefined): boolean {
  return job !== undefined && TERMINAL.has(job.status)
}

/** Follow a job live over SSE (reconnecting when a stream ends); poll if streaming fails. */
export function useJob(jobId: string | undefined): Job | undefined {
  const [job, setJob] = useState<Job>()

  useEffect(() => {
    if (!jobId) return undefined
    const abort = new AbortController()
    const { signal } = abort

    async function stream(id: string): Promise<boolean> {
      const response = await authorizedFetch(`/api/v1/jobs/${id}/events`, { signal })
      if (!response.ok || !response.body) throw new Error(`events: HTTP ${response.status}`)
      for await (const data of eventData(response.body)) {
        const next: unknown = JSON.parse(data)
        if (!isJob(next)) continue
        setJob(next)
        if (TERMINAL.has(next.status)) return true
      }
      return false
    }

    async function poll(id: string) {
      while (!signal.aborted) {
        const next = unwrap(
          await api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: id } }, signal })
        )
        setJob(next)
        if (TERMINAL.has(next.status)) return
        await new Promise((resolve) => setTimeout(resolve, 1500))
      }
    }

    async function follow(id: string) {
      try {
        while (!signal.aborted && !(await stream(id))) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
        }
      } catch {
        if (!signal.aborted) await poll(id).catch(() => undefined)
      }
    }

    void follow(jobId)
    return () => abort.abort()
  }, [jobId])

  return jobId ? job : undefined
}
