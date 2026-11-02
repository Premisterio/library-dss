import type { AnalyticsKey } from "@/api/types"

/** Analytics sections shown as tabs; the overview has its own page. */
export const ANALYTICS_TABS: readonly AnalyticsKey[] = [
  "usage",
  "content",
  "segments",
  "search",
  "subscriptions",
  "cohorts",
]

/** Every section, in the order reports list them. */
export const ALL_SECTIONS: readonly AnalyticsKey[] = ["overview", ...ANALYTICS_TABS]

export function isAnalyticsTab(value: string | undefined): value is AnalyticsKey {
  return ANALYTICS_TABS.some((key) => key === value)
}
