/** Presentation of the API's raw numbers and ISO dates (the API never formats). */
import type { Unit } from "@/api/types"

const LOCALE = "uk-UA"

/** Shown for a value the data does not have. */
export const EMPTY = "—"

function number(value: number, maximumFractionDigits: number): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(value)
}

export function formatValue(value: number | null | undefined, unit: Unit): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY
  switch (unit) {
    case "ratio":
      return new Intl.NumberFormat(LOCALE, { style: "percent", maximumFractionDigits: 1 }).format(
        value
      )
    case "UAH":
      return `${number(value, value >= 1000 ? 0 : 2)} грн`
    case "minutes":
      return value >= 600 ? `${number(value / 60, 0)} год` : `${number(value, 1)} хв`
    case "days":
      return `${number(value, 1)} дн.`
    case "rating":
      return number(value, 2)
    default:
      return number(value, 1)
  }
}

/** Short value for chart axes. */
export function formatAxis(value: number, unit: Unit): string {
  if (unit === "ratio") return formatValue(value, unit)
  return new Intl.NumberFormat(LOCALE, { notation: "compact", maximumFractionDigits: 1 }).format(
    value
  )
}

function parseDate(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number)
  return new Date(Date.UTC(year ?? 1970, (month ?? 1) - 1, day ?? 1))
}

/** "28.09.2026" for days and weeks. */
export function formatDay(iso: string | null | undefined): string {
  if (!iso) return EMPTY
  return new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", dateStyle: "short" }).format(
    parseDate(iso)
  )
}

/** "вер. 2026" for month starts. */
export function formatMonth(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", month: "short", year: "numeric" })
    .format(parseDate(iso))
    .replace(/\s*р\.$/, "")
}

/** "07:00" for an hour of the day. */
export function formatHour(hour: number | string): string {
  return `${String(hour).padStart(2, "0")}:00`
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso)
  )
}

export function windowText(days: number | null | undefined): string {
  return days ? `за ${days} днів` : ""
}
