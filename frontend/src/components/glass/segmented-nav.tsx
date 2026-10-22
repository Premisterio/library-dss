import { NavLink } from "react-router"

import { cn } from "@/lib/utils"

/**
 * A segmented control that switches between closely related views, for the toolbar. Segments are
 * links (the view is in the URL); the current one is marked for assistive technology too.
 * It sits on the toolbar's glass, so it is a recessed track, not glass of its own.
 */
export function SegmentedNav({
  label,
  items,
}: {
  label: string
  items: { to: string; label: string }[]
}) {
  return (
    <nav aria-label={label} className="max-w-full">
      <ul className="flex w-max items-center gap-0.5 rounded-full bg-fill p-0.5">
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex h-8 items-center rounded-full px-3 text-[13px] whitespace-nowrap transition-colors outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive
                    ? "bg-glass-selected font-semibold text-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-glass-hover hover:text-foreground"
                )
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
