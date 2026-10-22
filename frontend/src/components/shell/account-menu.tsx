import { LogOutIcon } from "lucide-react"
import { useNavigate } from "react-router"

import { useAuth, useLogout } from "@/api/auth"
import { useAppearance, type Appearance } from "@/app/appearance"
import { paths } from "@/app/paths"
import { Button } from "@/components/ui/button"
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

/** The analyst, the appearance and sign-out, at the trailing edge of the toolbar. */
export function AccountMenu() {
  const { analyst } = useAuth()
  const { appearance, setAppearance } = useAppearance()
  const logout = useLogout()
  const navigate = useNavigate()
  // An explicit sign-out starts the next session from the dataset list, not from this page.
  // (mutateAsync: the shell unmounts as the session ends, which would drop a mutate callback.)
  async function signOut() {
    await logout.mutateAsync().catch(() => undefined)
    void navigate(paths.login, { replace: true })
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="secondary"
          size="icon"
          aria-label={`Обліковий запис: ${analyst?.name ?? ""}`}
          className="text-xs font-semibold"
        >
          {initials(analyst?.name)}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
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
  )
}
