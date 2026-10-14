import createClient, { type ClientOptions } from "openapi-fetch"

import type { components, paths } from "./schema"

export type { components, paths }

/** Request/response models of the API, e.g. `Schemas["HealthOut"]`. */
export type Schemas = components["schemas"]

/**
 * Creates a typed API client. Leave `baseUrl` empty for same-origin deployments
 * (Caddy in prod, the Vite proxy in dev); paths already include `/api/v1`.
 */
export function createApiClient(options: ClientOptions = {}) {
  return createClient<paths>({ baseUrl: "", ...options })
}

export type ApiClient = ReturnType<typeof createApiClient>
