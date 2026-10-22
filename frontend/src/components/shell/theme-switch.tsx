import { MonitorIcon, MoonIcon, SunIcon } from "lucide-react"

import { IconButton } from "@/components/common/icon-button"
import { useTheme } from "@/components/theme-provider"

const THEMES = [
  { value: "light", icon: SunIcon, title: "Світла тема" },
  { value: "dark", icon: MoonIcon, title: "Темна тема" },
  { value: "system", icon: MonitorIcon, title: "Як у системі" },
] as const

/** Cycles light → dark → system; the label says what the next click does. */
export function ThemeSwitch() {
  const { theme, setTheme } = useTheme()
  const index = THEMES.findIndex((t) => t.value === theme)
  const current = THEMES[index] ?? THEMES[2]
  const next = THEMES[(index + 1) % THEMES.length] ?? THEMES[0]
  return (
    <IconButton
      icon={current.icon}
      label={`${current.title} (натисніть для: ${next.title.toLowerCase()})`}
      onClick={() => setTheme(next.value)}
    />
  )
}
