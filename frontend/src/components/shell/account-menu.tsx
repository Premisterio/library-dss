import { ChevronsUpDownIcon, LogOutIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { useAuth, useLogout } from "@/api/auth"
import { useAppearance, type Appearance } from "@/app/appearance"
import { paths } from "@/app/paths"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

const APPEARANCES: { value: Appearance; label: string }[] = [
  { value: "system", label: "Як у системі" },
  { value: "light", label: "Світле" },
  { value: "dark", label: "Темне" },
]

function isAppearance(value: string): value is Appearance {
  return APPEARANCES.some((option) => option.value === value)
}

function initials(name: string | undefined): string {
  const letters = (name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word[0])
    .join("")
  return letters.slice(0, 2).toUpperCase() || "…"
}

/**
 * The analyst, the appearance and sign-out, in the sidebar's footer. Collapsed to icons, the
 * sidebar keeps the avatar and the menu opens beside it.
 */
export function AccountMenu() {
  const { analyst } = useAuth()
  const { appearance, setAppearance } = useAppearance()
  const logout = useLogout()
  const navigate = useNavigate()
  const { isMobile } = useSidebar()
  // An explicit sign-out starts the next session from the dataset list, not from this page.
  // (mutateAsync: the shell unmounts as the session ends, which would drop a mutate callback.)
  async function signOut() {
    await logout.mutateAsync().catch(() => undefined)
    void navigate(paths.login, { replace: true })
  }
  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton size="lg" aria-label={`Обліковий запис: ${analyst?.name ?? ""}`}>
              <span
                aria-hidden
                className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-xs font-semibold"
              >
                {initials(analyst?.name)}
              </span>
              <span className="flex min-w-0 flex-col leading-tight">
                <span className="truncate text-sm font-medium">{analyst?.name}</span>
                <span className="truncate text-xs text-muted-foreground">{analyst?.email}</span>
              </span>
              <ChevronsUpDownIcon className="ml-auto size-4 text-muted-foreground" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
            className="w-56"
          >
            <DropdownMenuLabel className="flex flex-col">
              <span className="truncate text-sm font-medium text-foreground">{analyst?.name}</span>
              <span className="truncate text-xs font-normal text-muted-foreground">
                {analyst?.email}
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
              Оформлення
            </DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={appearance}
              onValueChange={(value) => {
                if (isAppearance(value)) setAppearance(value)
              }}
            >
              {APPEARANCES.map((option) => (
                <DropdownMenuRadioItem key={option.value} value={option.value}>
                  {option.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem disabled={logout.isPending} onSelect={() => void signOut()}>
              <LogOutIcon />
              Вийти
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
