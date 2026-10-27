import { UsersRoundIcon } from "lucide-react"
import { Link } from "react-router"

import { paths } from "@/app/paths"
import { EmptyState } from "@/components/common/empty-state"
import { Button } from "@/components/ui/button"

/** The views that rely on the active model, before one is activated. */
export function NoActiveRun({ datasetId }: { datasetId: number }) {
  return (
    <EmptyState
      icon={UsersRoundIcon}
      title="Немає активної моделі"
      description="Навчіть модель відтоку й активуйте її: тоді тут з'являться читачі з найвищим ризиком, причини та план утримання."
    >
      <Button asChild>
        <Link to={paths.churnModel(datasetId)}>До моделі</Link>
      </Button>
    </EmptyState>
  )
}
