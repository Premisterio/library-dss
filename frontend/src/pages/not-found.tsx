import { Link } from "react-router"

import { paths } from "@/app/paths"
import { EmptyState } from "@/components/common/empty-state"
import { Button } from "@/components/ui/button"

export function NotFound({ className = "min-h-svh" }: { className?: string }) {
  return (
    <EmptyState
      title="Сторінку не знайдено"
      description="Можливо, посилання застаріло."
      className={className}
    >
      <Button asChild>
        <Link to={paths.datasets}>До датасетів</Link>
      </Button>
    </EmptyState>
  )
}
