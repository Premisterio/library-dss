import type { UseQueryResult } from "@tanstack/react-query"
import type { ReactNode } from "react"

import { ErrorAlert } from "@/components/common/error-alert"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

/**
 * The three states of a query in one place: a skeleton while loading, the error, or the data.
 * `empty` replaces the data when `isEmpty` says there is nothing to show.
 */
export function QueryView<T>({
  query,
  skeletonClassName,
  errorDetails,
  isEmpty,
  empty,
  children,
}: {
  query: UseQueryResult<T>
  skeletonClassName?: string
  errorDetails?: ReactNode
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <Skeleton className={cn("h-24 w-full", skeletonClassName)} />
  if (query.isError) return <ErrorAlert error={query.error}>{errorDetails}</ErrorAlert>
  if (empty !== undefined && isEmpty?.(query.data)) return empty
  return children(query.data)
}
