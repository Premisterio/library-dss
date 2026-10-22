import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { expectOk, unwrap } from "@/api/problem"
import type { ExportFormat, Report, SectionKey } from "@/api/types"
import { fileNameFrom } from "@/lib/content-disposition"

/** Long enough for every browser to start the download before the blob is released. */
const REVOKE_AFTER_MS = 40_000

export function useReports(datasetId: number) {
  return useQuery({
    queryKey: keys.reportList(datasetId),
    queryFn: async () =>
      unwrap(
        await api.GET("/api/v1/reports", {
          params: { query: { dataset_id: datasetId, limit: 100 } },
        })
      ).items,
  })
}

export function useCreateReport(datasetId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ title, sections }: { title: string; sections: SectionKey[] }) =>
      unwrap(
        await api.POST("/api/v1/reports", { body: { dataset_id: datasetId, title, sections } })
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.reportList(datasetId) }),
  })
}

export function useDeleteReport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (report: Report) =>
      expectOk(
        await api.DELETE("/api/v1/reports/{report_id}", {
          params: { path: { report_id: report.id } },
        })
      ),
    onSuccess: (_, report) =>
      void queryClient.invalidateQueries({ queryKey: keys.reportList(report.dataset_id) }),
  })
}

function saveFile(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), REVOKE_AFTER_MS)
}

/** Download an export: the browser cannot add the access token to a plain link. */
export function useDownloadReport() {
  return useMutation({
    mutationFn: async ({ report, format }: { report: Report; format: ExportFormat }) => {
      const result = await api.GET("/api/v1/reports/{report_id}/export", {
        params: { path: { report_id: report.id }, query: { format } },
        parseAs: "blob",
      })
      const blob = unwrap(result)
      const fallback = `report-${report.id}.${format === "csv" ? "zip" : format}`
      saveFile(blob, fileNameFrom(result.response.headers.get("Content-Disposition"), fallback))
    },
  })
}
