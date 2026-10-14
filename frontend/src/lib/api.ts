import { createApiClient, type ApiClient, type Schemas } from "@library-dss/api-client"

/** Same-origin client: Vite proxies /api in dev, Caddy in prod. */
export const api = createApiClient()

export type Health = Schemas["HealthOut"]

export async function fetchHealth(client: ApiClient = api): Promise<Health> {
  const { data, error } = await client.GET("/api/v1/health")
  if (error) throw new Error(`API error: ${error.code}`)
  return data
}
