import { createContext, useContext, useMemo, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"

import { Glass } from "@/components/glass/glass"

type Slots = {
  center: HTMLElement | null
  trailing: HTMLElement | null
  setCenter: (node: HTMLElement | null) => void
  setTrailing: (node: HTMLElement | null) => void
}

const ToolbarContext = createContext<Slots | null>(null)

function useToolbar(): Slots {
  const slots = useContext(ToolbarContext)
  if (!slots) throw new Error("The toolbar is used outside ToolbarProvider")
  return slots
}

/** Lets pages put their own controls into the shell's toolbar (`ToolbarSlot`). */
export function ToolbarProvider({ children }: { children: ReactNode }) {
  const [center, setCenter] = useState<HTMLElement | null>(null)
  const [trailing, setTrailing] = useState<HTMLElement | null>(null)
  const value = useMemo(() => ({ center, trailing, setCenter, setTrailing }), [center, trailing])
  return <ToolbarContext.Provider value={value}>{children}</ToolbarContext.Provider>
}

/**
 * The floating glass toolbar: leading controls and the page title, a center area and a trailing
 * area that pages fill through `ToolbarSlot`, then the shell's own `actions`. Content scrolls
 * beneath it and fades at its edge.
 */
export function GlassToolbar({
  leading,
  title,
  actions,
}: {
  leading?: ReactNode
  title?: ReactNode
  actions?: ReactNode
}) {
  const { setCenter, setTrailing } = useToolbar()
  return (
    <div className="scroll-edge sticky top-0 z-20 px-3 pt-3 md:px-4">
      <Glass asChild>
        {/* Below xl the center area takes a second row, so view switching never gets squeezed out. */}
        <header className="flex min-h-12 flex-wrap items-center gap-x-2 gap-y-1.5 rounded-[1.75rem] py-1.5 pr-1.5 pl-2">
          {leading}
          <h1 className="shrink-0 truncate text-[15px] font-semibold">{title}</h1>
          <div
            ref={setCenter}
            className="order-last flex w-full justify-center overflow-x-auto empty:hidden xl:order-0 xl:w-auto xl:min-w-0 xl:flex-1"
          />
          <div ref={setTrailing} className="ml-auto flex min-w-0 items-center gap-2" />
          {actions}
        </header>
      </Glass>
    </div>
  )
}

/** Renders its children in the toolbar: `center` for view switching, `trailing` for context. */
export function ToolbarSlot({
  side,
  children,
}: {
  side: "center" | "trailing"
  children: ReactNode
}) {
  const slots = useToolbar()
  const node = side === "center" ? slots.center : slots.trailing
  return node ? createPortal(children, node) : null
}
