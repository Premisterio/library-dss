import { useLabel } from "@/api/enums"
import type { ChurnScore } from "@/api/types"
import { ReasonList } from "@/components/churn/reason-list"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatLocalDay, formatValue } from "@/lib/format"

/** The members at risk, the riskiest first, with their reasons; a member opens their card. */
export function RiskTable({
  scores,
  timezone,
  onOpen,
}: {
  scores: ChurnScore[]
  timezone: string
  onOpen: (userId: string) => void
}) {
  const label = useLabel()
  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-right">№</TableHead>
            <TableHead>Читач</TableHead>
            <TableHead className="text-right">Ризик відтоку</TableHead>
            <TableHead>Тариф</TableHead>
            <TableHead>Продовження</TableHead>
            <TableHead>Чому</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {scores.map((score) => (
            <TableRow key={score.user_id} className="align-top">
              <TableCell className="text-right text-muted-foreground tabular-nums">
                {score.rank}
              </TableCell>
              <TableCell>
                <Button
                  variant="link"
                  size="sm"
                  className="h-auto p-0"
                  onClick={() => onOpen(score.user_id)}
                >
                  {score.user_id}
                </Button>
              </TableCell>
              <TableCell className="text-right font-medium tabular-nums">
                {formatValue(score.probability, "ratio")}
              </TableCell>
              <TableCell>{label("plan", score.plan)}</TableCell>
              <TableCell className="tabular-nums">
                {formatLocalDay(score.period_end, timezone)}
              </TableCell>
              <TableCell className="min-w-72 text-sm whitespace-normal">
                <ReasonList reasons={score.reasons} />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
