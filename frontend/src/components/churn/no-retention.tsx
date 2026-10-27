import { UserMinusIcon } from "lucide-react"

import { EmptyState } from "@/components/common/empty-state"

/** The dataset cannot be used to predict churn. */
export function NoRetention() {
  return (
    <EmptyState
      icon={UserMinusIcon}
      title="Відтік для цього датасету не прогнозується"
      description="Потрібні періоди платних підписок із результатами продовження та кампанія утримання. Їх містять датасети табличного формату (libsim)."
    />
  )
}
