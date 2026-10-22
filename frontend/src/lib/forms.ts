/** A text field of a submitted form (files and missing fields give ""), trimmed unless asked not to. */
export function formText(form: FormData, name: string, { trim = true } = {}): string {
  const value = form.get(name)
  if (typeof value !== "string") return ""
  return trim ? value.trim() : value
}
