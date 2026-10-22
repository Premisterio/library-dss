/** The file name from Content-Disposition: `filename*` (RFC 6266, UTF-8) wins over `filename`. */
export function fileNameFrom(disposition: string | null, fallback: string): string {
  if (!disposition) return fallback
  const extended = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(disposition)
  if (extended?.[1]) {
    try {
      return decodeURIComponent(extended[1].trim())
    } catch {
      // a malformed escape: fall through to the plain name
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/i.exec(disposition)
  return plain?.[1]?.trim() || fallback
}
