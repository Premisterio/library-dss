import { useLabel } from "@/api/enums"
import type { Reason } from "@/api/types"
import { effectText, reasonText } from "@/lib/churn"

/** Why a member's risk is high, strongest reason first, each with what it adds to the risk. */
export function ReasonList({ reasons }: { reasons: Reason[] }) {
  const label = useLabel()
  if (reasons.length === 0) {
    return <span className="text-muted-foreground">Нічого не вирізняється</span>
  }
  return (
    <ul className="flex flex-col gap-0.5">
      {reasons.map((reason) => (
        <li key={reason.feature}>
          {reasonText(reason, label)}{" "}
          <span className="whitespace-nowrap text-muted-foreground tabular-nums">
            {effectText(reason)}
          </span>
        </li>
      ))}
    </ul>
  )
}
