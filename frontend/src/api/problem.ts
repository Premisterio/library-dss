import type { Problem } from "@/api/types"
import { messageFor } from "@/lib/messages"

/** An error answer of the API (RFC 9457), carrying its stable `code`. */
export class ApiProblem extends Error {
  readonly problem: Problem

  constructor(problem: Problem) {
    super(problem.detail ?? problem.code)
    this.name = "ApiProblem"
    this.problem = problem
  }
}

function isProblem(value: unknown): value is Problem {
  return (
    typeof value === "object" &&
    value !== null &&
    "code" in value &&
    typeof value.code === "string" &&
    "status" in value &&
    typeof value.status === "number" &&
    "title" in value
  )
}

/** A body that is not Problem Details (a proxy error page, say) still gets a code: `http.<status>`. */
function asProblem(error: unknown, response: Response): Problem {
  if (isProblem(error)) return error
  return {
    type: "about:blank",
    title: response.statusText || "Error",
    status: response.status,
    detail: null,
    code: `http.${response.status}`,
    errors: [],
  }
}

/** Unwrap an openapi-fetch result: the data, or an ApiProblem. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw new ApiProblem(asProblem(result.error, result.response))
  }
  return result.data
}

/** For answers without a body (204): throws an ApiProblem unless the response is ok. */
export function expectOk(result: { error?: unknown; response: Response }): void {
  if (result.error !== undefined || !result.response.ok) {
    throw new ApiProblem(asProblem(result.error, result.response))
  }
}

/** A user-facing message for anything an API call throws. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiProblem) {
    const { code, detail, status } = error.problem
    return messageFor(code, detail, status)
  }
  if (error instanceof TypeError) return "Немає зв'язку з сервером."
  return error instanceof Error ? error.message : String(error)
}
