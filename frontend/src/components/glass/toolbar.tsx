import { createContext, useContext, useMemo, useState, type ReactNode } from "react"
import { createPortal } from "react-dom"

import { Glass } from "@/components/glass/glass"

type Slots = {
  center: HTMLElement | null
  setCenter: (node: HTMLElement | null) => void
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
  const value = useMemo(() => ({ center, setCenter }), [center])
  return <ToolbarContext.Provider value={value}>{children}</ToolbarContext.Provider>
}

/**
 * The floating glass toolbar: leading controls, the page title and a center area that pages fill
 * through `ToolbarSlot`. Content scrolls beneath it and fades at its edge.
 */
export function GlassToolbar({ leading, title }: { leading?: ReactNode; title?: ReactNode }) {
  const { setCenter } = useToolbar()
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
        </header>
      </Glass>
    </div>
  )
}

/** Renders its children in the toolbar's center area, for switching between related views. */
export function ToolbarSlot({ children }: { children: ReactNode }) {
  const { center } = useToolbar()
  return center ? createPortal(children, center) : null
}
