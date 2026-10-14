import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { fetchHealth } from "@/lib/api"

export function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => fetchHealth() })

  return (
    <main className="mx-auto flex min-h-svh max-w-2xl flex-col gap-6 p-6">
      <header>
        <h1 className="text-2xl font-semibold">СППР онлайн-бібліотеки</h1>
        <p className="text-sm text-muted-foreground">Версія 2 у розробці: каркас проєкту (M0)</p>
      </header>
      <section aria-labelledby="api-status" className="flex flex-col gap-3 rounded-xl border p-4">
        <h2 id="api-status" className="font-medium">
          Стан API
        </h2>
        {health.isPending && <p>Перевіряємо…</p>}
        {health.isError && (
          <p className="text-destructive">API недоступне: {health.error.message}</p>
        )}
        {health.isSuccess && <p>Працює, версія {health.data.version}</p>}
        <Button variant="outline" className="self-start" onClick={() => void health.refetch()}>
          Оновити
        </Button>
      </section>
    </main>
  )
}
