import { authorizedFetch } from "@/lib/api"

/** The file name from Content-Disposition: `filename*` (RFC 6266, UTF-8) wins over `filename`. */
export function fileNameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback
  const extended = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition)
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim())
    } catch {
      // fall through to the plain name
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(disposition)
  return plain?.[1]?.trim() || fallback
}

/** Download a protected file (the browser cannot add the access token to a plain link). */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await authorizedFetch(path)
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const name = fileNameFrom(response.headers.get("Content-Disposition"), fallbackName)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement("a")
  link.href = url
  link.download = name
  document.body.append(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
