/** A text field of a submitted form (files and missing fields give ""). */
export function formText(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === "string" ? value.trim() : ""
}
