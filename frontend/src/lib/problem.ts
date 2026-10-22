import { ApiProblem } from "@/lib/api"

/** Ukrainian messages for the stable error codes of the API (RFC 9457 `code`). */
const MESSAGES: Record<string, string> = {
  "auth.invalid_credentials": "Неправильний e-mail або пароль.",
  "auth.not_authenticated": "Сесія завершилась. Увійдіть знову.",
  "auth.token_expired": "Сесія завершилась. Увійдіть знову.",
  "auth.token_invalid": "Сесія завершилась. Увійдіть знову.",
  "auth.token_revoked": "Сесія завершилась. Увійдіть знову.",
  "dataset.duplicate": "Цей файл уже завантажено.",
  "dataset.too_large": "Файл завеликий.",
  "dataset.unreadable": "Файл не є коректним JSON (або gzip-архівом з JSON).",
  "dataset.invalid": "У файлі є помилки.",
  "dataset.unsupported_version": "Невідомий формат файлу.",
  "dataset.not_ready": "Датасет ще не готовий.",
  "dataset.busy": "Датасет зараз імпортується, спробуйте пізніше.",
  "dataset.not_found": "Датасет не знайдено.",
  "report.not_found": "Звіт не знайдено.",
  "job.not_found": "Задачу не знайдено.",
  "analytics.missing": "Аналітику ще не пораховано.",
  "job.crashed": "Імпорт аварійно завершився.",
  "job.interrupted": "Імпорт перервано: фоновий виконавець зупинився.",
  "request.invalid": "Некоректний запит.",
  "system.database_unavailable": "База даних недоступна.",
}

export function messageFor(code: string, detail?: string | null): string {
  return MESSAGES[code] ?? detail ?? code
}

/** A user-facing message for anything thrown by an API call. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiProblem) return messageFor(error.problem.code, error.problem.detail)
  if (error instanceof TypeError) return "Немає зв'язку з сервером."
  return error instanceof Error ? error.message : String(error)
}
