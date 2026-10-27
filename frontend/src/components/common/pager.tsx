import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { formatValue } from "@/lib/format"

/** "1–50 з 930" with the previous and next pages of a list served in pages. */
export function Pager({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number
  limit: number
  total: number
  onChange: (offset: number) => void
}) {
  const last = Math.min(offset + limit, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
      <span className="text-muted-foreground tabular-nums">
        {total === 0
          ? "Нічого не знайдено"
          : `${formatValue(offset + 1, "count")}–${formatValue(last, "count")} з ${formatValue(total, "count")}`}
      </span>
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          <ChevronLeftIcon />
          Назад
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={last >= total}
          onClick={() => onChange(offset + limit)}
        >
          Далі
          <ChevronRightIcon />
        </Button>
      </div>
    </div>
  )
}
