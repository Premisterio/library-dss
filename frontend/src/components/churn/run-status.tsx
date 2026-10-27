import {
  CircleAlertIcon,
  CircleCheckIcon,
  ClockIcon,
  LoaderCircleIcon,
  StarIcon,
  type LucideIcon,
} from "lucide-react"

import { useLabel } from "@/api/enums"
import type { ChurnRun } from "@/api/types"
import { StatusPill } from "@/components/common/status-pill"

const STATUS: Record<
  ChurnRun["status"],
  { tone: "good" | "critical" | "neutral"; icon: LucideIcon; spinning?: boolean }
> = {
  queued: { tone: "neutral", icon: ClockIcon },
  running: { tone: "neutral", icon: LoaderCircleIcon, spinning: true },
  succeeded: { tone: "good", icon: CircleCheckIcon },
  failed: { tone: "critical", icon: CircleAlertIcon },
}

/** Where a run's training stands. */
export function RunStatus({ run }: { run: ChurnRun }) {
  const label = useLabel()
  const { tone, icon, spinning } = STATUS[run.status]
  return (
    <StatusPill tone={tone} icon={icon} spinning={spinning}>
      {label("job_status", run.status)}
    </StatusPill>
  )
}

/** The run that decisions on its dataset use. */
export function ActivePill() {
  return (
    <StatusPill tone="good" icon={StarIcon}>
      Активна
    </StatusPill>
  )
}
