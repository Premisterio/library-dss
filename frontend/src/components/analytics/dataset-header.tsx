import type { Dataset } from "@/api/types"
import { CapabilityBadges } from "@/components/datasets/dataset-badges"
import { formatDay } from "@/lib/format"

export function DatasetHeader({ dataset }: { dataset: Dataset }) {
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{dataset.name}</h2>
        <p className="text-sm text-muted-foreground">
          Станом на {formatDay(dataset.as_of)} · {dataset.timezone}
        </p>
      </div>
      <CapabilityBadges capabilities={dataset.capabilities} />
    </div>
  )
}
