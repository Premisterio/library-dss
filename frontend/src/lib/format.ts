/** Presentation of the API's raw numbers and ISO dates (the API never formats). */
import type { Unit } from "@/api/types"

const LOCALE = "uk-UA"

/** Shown for a value the data does not have. */
export const EMPTY = "—"

function number(value: number, maximumFractionDigits: number): string {
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits }).format(value)
}

/** A number with a fixed count of decimals, for scores such as AUC (0,688). */
export function formatDecimal(value: number | null | undefined, digits: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) return EMPTY
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)
}

/** A change of a probability in percentage points: 0.112 → "+11,2 в. п.". */
export function formatPoints(fraction: number): string {
  return `${fraction > 0 ? "+" : ""}${number(fraction * 100, 1)} в. п.`
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

/** The local date of an instant in the dataset's time zone: "05.10.26". */
export function formatLocalDay(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALE, { timeZone, dateStyle: "short" }).format(new Date(iso))
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat(LOCALE, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso)
  )
}

export function windowText(days: number | null | undefined): string {
  return days ? `за ${days} днів` : ""
}
