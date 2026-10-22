/**
 * Light or dark. It follows the system unless the analyst picks one in the account menu; the
 * choice is kept in this browser. The resolved value is `data-theme` on <html>, which the tokens
 * and the Tailwind `dark:` variant read. index.html applies it before the first paint.
 */
import { useSyncExternalStore } from "react"

export type Appearance = "system" | "light" | "dark"

const STORAGE_KEY = "appearance" // also read by the inline script in index.html
const DARK_QUERY = "(prefers-color-scheme: dark)"

const listeners = new Set<() => void>()

export function resolveAppearance(appearance: Appearance, systemIsDark: boolean): "light" | "dark" {
  if (appearance === "system") return systemIsDark ? "dark" : "light"
  return appearance
}

function stored(): Appearance {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return value === "light" || value === "dark" ? value : "system"
  } catch {
    return "system" // storage blocked: follow the system
  }
}

function systemDark(): boolean {
  return window.matchMedia(DARK_QUERY).matches
}

function apply() {
  document.documentElement.dataset.theme = resolveAppearance(stored(), systemDark())
  for (const listener of listeners) listener()
}

export function setAppearance(appearance: Appearance) {
  try {
    if (appearance === "system") localStorage.removeItem(STORAGE_KEY)
    else localStorage.setItem(STORAGE_KEY, appearance)
  } catch {
    // storage blocked: the choice lasts for this page only
  }
  apply()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  const media = window.matchMedia(DARK_QUERY)
  const onStorage = (event: StorageEvent) => {
    if (event.key === STORAGE_KEY) apply()
  }
  media.addEventListener("change", apply)
  window.addEventListener("storage", onStorage)
  return () => {
    listeners.delete(listener)
    media.removeEventListener("change", apply)
    window.removeEventListener("storage", onStorage)
  }
}

/** The analyst's choice and what it resolves to now. */
export function useAppearance() {
  const appearance = useSyncExternalStore(subscribe, stored)
  const resolved = useSyncExternalStore(subscribe, () => resolveAppearance(stored(), systemDark()))
  return { appearance, resolved, setAppearance }
}
