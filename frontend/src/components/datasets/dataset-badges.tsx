import { useLabel } from "@/api/enums"
import type { Capability, DatasetStatus } from "@/api/types"
import { Badge } from "@/components/ui/badge"

const STATUS_VARIANT = {
  pending: "outline",
  importing: "secondary",
  ready: "default",
  failed: "destructive",
} as const satisfies Record<DatasetStatus, string>

export function StatusBadge({ status }: { status: DatasetStatus }) {
  const label = useLabel()
  return <Badge variant={STATUS_VARIANT[status]}>{label("dataset_status", status)}</Badge>
}

export function CapabilityBadges({ capabilities }: { capabilities: Capability[] }) {
  const label = useLabel()
  return (
    <div className="flex flex-wrap gap-1">
      {capabilities.map((capability) => (
        <Badge key={capability} variant="outline">
          {label("capability", capability)}
        </Badge>
      ))}
    </div>
  )
}
