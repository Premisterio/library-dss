import {
  CircleAlertIcon,
  CircleCheckIcon,
  ClockIcon,
  LoaderCircleIcon,
  type LucideIcon,
} from "lucide-react"

import { useLabel } from "@/api/enums"
import type { Capability, DatasetStatus } from "@/api/types"
import { StatusPill } from "@/components/common/status-pill"
import { Badge } from "@/components/ui/badge"

const STATUS: Record<
  DatasetStatus,
  { tone: "good" | "critical" | "neutral"; icon: LucideIcon; spinning?: boolean }
> = {
  pending: { tone: "neutral", icon: ClockIcon },
  importing: { tone: "neutral", icon: LoaderCircleIcon, spinning: true },
  ready: { tone: "good", icon: CircleCheckIcon },
  failed: { tone: "critical", icon: CircleAlertIcon },
}

export function StatusBadge({ status }: { status: DatasetStatus }) {
  const label = useLabel()
  const { tone, icon, spinning } = STATUS[status]
  return (
    <StatusPill tone={tone} icon={icon} spinning={spinning}>
      {label("dataset_status", status)}
    </StatusPill>
  )
}

export function CapabilityBadges({ capabilities }: { capabilities: Capability[] }) {
  const label = useLabel()
  return (
    <div className="flex flex-wrap gap-1">
      {capabilities.map((capability) => (
        <Badge key={capability} variant="secondary" className="font-normal">
          {label("capability", capability)}
        </Badge>
      ))}
    </div>
  )
}
