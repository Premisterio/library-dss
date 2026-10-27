import { useParams } from "react-router"

import type { AnalyticsKey } from "@/api/types"

/** Every path of the app; links and redirects build them here. */
export const paths = {
  login: "/login",
  datasets: "/datasets",
  dataset: (id: number) => `/d/${id}`,
  analytics: (id: number, section?: AnalyticsKey) =>
    section ? `/d/${id}/analytics/${section}` : `/d/${id}/analytics`,
  reports: (id: number) => `/d/${id}/reports`,
  churnModel: (id: number, run?: number) =>
    run === undefined ? `/d/${id}/churn` : `/d/${id}/churn?run=${run}`,
  churnRisk: (id: number) => `/d/${id}/churn/risk`,
}

/** A database id from the URL: digits only, so `abc`, `1e1` or `-1` are not ids. */
export function parseId(value: string | undefined): number | undefined {
  if (!value || !/^[1-9]\d*$/.test(value)) return undefined
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : undefined
}

/** The `:datasetId` of the current route, when it is a valid id. */
export function useDatasetId(): number | undefined {
  return parseId(useParams().datasetId)
}
