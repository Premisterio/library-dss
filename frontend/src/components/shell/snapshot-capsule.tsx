import { CalendarClockIcon } from "lucide-react"

import type { Dataset } from "@/api/types"
import { formatDay } from "@/lib/format"

/**
 * Which data the page shows: the dataset and its snapshot date. It stays in the toolbar while the
 * page scrolls, so every number on screen is read against its "as of".
 */
export function SnapshotCapsule({ dataset }: { dataset: Dataset }) {
  return (
    <div
      className="flex min-w-0 items-center gap-2 rounded-full bg-fill py-1 pr-3 pl-2 text-[13px]"
      title={`Часовий пояс: ${dataset.timezone}`}
    >
      <CalendarClockIcon aria-hidden className="size-4 shrink-0 text-muted-foreground" />
      <span className="truncate font-medium">{dataset.name}</span>
      <span className="shrink-0 text-muted-foreground">
        <span className="hidden sm:inline">станом на </span>
        {formatDay(dataset.as_of)}
      </span>
    </div>
  )
}
