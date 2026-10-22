import type { LucideIcon } from "lucide-react"
import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

const ICON_TONE = {
  good: "text-status-good",
  critical: "text-status-critical",
  neutral: "text-muted-foreground",
} as const

/**
 * A state: a coloured icon and a label in text colour, so the state never rests on colour alone.
 * `spinning` turns the icon for work in progress, unless Reduce Motion is on.
 */
export function StatusPill({
  tone,
  icon: Icon,
  spinning = false,
  children,
}: {
  tone: keyof typeof ICON_TONE
  icon: LucideIcon
  spinning?: boolean
  children: ReactNode
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-fill px-2 py-0.5 text-xs font-medium whitespace-nowrap text-foreground">
      <Icon
        aria-hidden
        className={cn("size-3.5 shrink-0", ICON_TONE[tone], spinning && "motion-safe:animate-spin")}
      />
      {children}
    </span>
  )
}
