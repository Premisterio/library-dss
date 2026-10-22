import type { LucideIcon } from "lucide-react"
import { Link, useMatch } from "react-router"

import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"

/**
 * A sidebar link, highlighted on its page (and below it, unless `end`). Only the current item's
 * icon takes the accent colour.
 */
export function NavItem({
  to,
  icon: Icon,
  children,
  end = false,
}: {
  to: string
  icon: LucideIcon
  children: string
  end?: boolean
}) {
  const active = useMatch({ path: to, end }) !== null
  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        asChild
        isActive={active}
        tooltip={children}
        className="data-active:[&_svg]:text-primary"
      >
        <Link to={to}>
          <Icon />
          <span>{children}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
}
