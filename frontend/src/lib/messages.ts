/** Ukrainian messages for the stable error codes of the API (RFC 9457 `code`). */

const SESSION_ENDED = "Сесія завершилась. Увійдіть знову."
const SERVER_ERROR = "Помилка сервера. Спробуйте пізніше."

const MESSAGES: Record<string, string> = {
  "auth.invalid_credentials": "Неправильний e-mail або пароль.",
  "auth.not_authenticated": SESSION_ENDED,
  "auth.token_expired": SESSION_ENDED,
  "auth.token_invalid": SESSION_ENDED,
  "auth.token_revoked": SESSION_ENDED,
  "auth.email_taken": "Цей e-mail уже зареєстровано.",
  "auth.password_too_short": "Пароль закороткий.",
  "auth.registration_disabled": "Реєстрацію вимкнено.",
  "dataset.duplicate": "Цей файл уже завантажено.",
  "dataset.too_large": "Файл завеликий.",
  "dataset.unreadable": "Файл не є коректним JSON (або gzip-архівом з JSON).",
  "dataset.invalid": "У файлі є помилки.",
  "dataset.unsupported_version": "Невідомий формат файлу.",
  "dataset.not_ready": "Датасет ще не готовий.",
  "dataset.busy": "Датасет зараз імпортується, спробуйте пізніше.",
  "dataset.not_found": "Датасет не знайдено.",
  "dataset.missing": "Датасет видалили до завершення імпорту.",
  "report.not_found": "Звіт не знайдено.",
  "job.not_found": "Задачу не знайдено.",
  "job.crashed": "Задача аварійно завершилась.",
  "job.interrupted": "Задачу перервано: фоновий виконавець зупинився.",
  "job.unknown_kind": "Невідомий тип задачі.",
  "analytics.missing": "Аналітику ще не пораховано.",
  "churn.not_supported": "У датасеті немає періодів підписок і кампанії утримання.",
  "churn.not_enough_history": "Замало історії: потрібні відтоки й продовження в кількох вікнах.",
  "churn.not_found": "Модель не знайдено.",
  "churn.not_trained": "Модель ще не навчено.",
  "churn.busy": "Модель зараз навчається, спробуйте пізніше.",
  "churn.member_not_scored": "Цей читач не в групі ризику.",
  "churn.missing": "Модель або датасет видалили до навчання.",
  "retention.no_effects":
    "Модель навчено до того, як з'явилась оцінка ефектів дій. Навчіть її ще раз.",
  "retention.no_campaign": "У датасеті немає кампанії, тож ефекти дій невідомі. Задайте їх вручну.",
  "retention.nobody_at_risk": "У групі ризику нікого немає.",
  "retention.not_active": "Затвердити можна лише план активної моделі.",
  "request.invalid": "Некоректний запит.",
  "server.error": SERVER_ERROR,
  "system.database_unavailable": "База даних недоступна.",
  "system.migrations_pending": "Сервер оновлюється. Спробуйте за хвилину.",
}

/** The message for a code; unknown codes fall back by status, then to the API's own detail. */
export function messageFor(code: string, detail?: string | null, status?: number): string {
  const known = MESSAGES[code]
  if (known) return known
  if (status !== undefined && status >= 500) return SERVER_ERROR
  if (code.startsWith("http.")) return `Запит не вдався (HTTP ${code.slice(5)}).`
  return detail || code
}
