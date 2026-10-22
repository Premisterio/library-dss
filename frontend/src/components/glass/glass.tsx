import { Slot } from "radix-ui"
import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

/**
 * A surface of the functional layer (DESIGN.md §4). `regular` for small floating controls,
 * `thick` for large or text-heavy ones. Never use it for content: cards, tables, charts.
 */
export function Glass({
  variant = "regular",
  asChild = false,
  className,
  ...props
}: ComponentProps<"div"> & { variant?: "regular" | "thick"; asChild?: boolean }) {
  const Component = asChild ? Slot.Root : "div"
  return (
    <Component
      data-glass={variant}
      className={cn(variant === "thick" ? "glass-thick" : "glass", className)}
      {...props}
    />
  )
}
