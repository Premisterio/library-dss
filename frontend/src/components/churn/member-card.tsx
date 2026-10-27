import { Fragment } from "react"

import { useLabel } from "@/api/enums"
import type { ChurnScoreDetail } from "@/api/types"
import { ReasonList } from "@/components/churn/reason-list"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { byGroup, featureValueText } from "@/lib/churn"
import { formatLocalDay, formatValue } from "@/lib/format"

/** Everything the model knew about one member at risk, next to the typical values. */
export function MemberCard({ score, timezone }: { score: ChurnScoreDetail; timezone: string }) {
  const label = useLabel()
  return (
    <div className="flex flex-col gap-4 text-sm">
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1">
        <dt className="text-muted-foreground">Ризик відтоку</dt>
        <dd className="font-semibold tabular-nums">{formatValue(score.probability, "ratio")}</dd>
        <dt className="text-muted-foreground">Тариф</dt>
        <dd>{label("plan", score.plan)}</dd>
        <dt className="text-muted-foreground">Продовження</dt>
        <dd className="tabular-nums">{formatLocalDay(score.period_end, timezone)}</dd>
      </dl>
      <section className="flex flex-col gap-1">
        <h3 className="font-semibold">Чому ризик високий</h3>
        <ReasonList reasons={score.reasons} />
      </section>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Ознака</TableHead>
            <TableHead className="text-right">Читач</TableHead>
            <TableHead className="text-right">Типово</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {byGroup(score.features).map(([group, features]) => (
            <Fragment key={group}>
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={3} className="pt-4 font-semibold">
                  {label("churn_feature_group", group)}
                </TableCell>
              </TableRow>
              {features.map((feature) => (
                <TableRow key={feature.feature}>
                  <TableCell className="whitespace-normal">
                    {label("churn_feature", feature.feature)}
                  </TableCell>
                  <TableCell className="text-right whitespace-normal tabular-nums">
                    {featureValueText(feature.value, feature, label)}
                  </TableCell>
                  <TableCell className="text-right whitespace-normal text-muted-foreground tabular-nums">
                    {featureValueText(feature.typical, feature, label)}
                  </TableCell>
                </TableRow>
              ))}
            </Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
