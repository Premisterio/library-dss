import { useLabel } from "@/api/enums"
import type { Chart } from "@/api/types"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { numberOf } from "@/lib/charts"
import { formatDecimal, formatValue } from "@/lib/format"

/** The titles on offer by TOPSIS, with SAW's place, stability and the decision. */
export function RankingTable({ ranking }: { ranking: Chart }) {
  const label = useLabel()
  return (
    <div className="max-h-[32rem] overflow-auto rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-right">№</TableHead>
            <TableHead>Назва</TableHead>
            <TableHead>Жанр</TableHead>
            <TableHead className="text-right">TOPSIS</TableHead>
            <TableHead className="text-right">№ за SAW</TableHead>
            <TableHead className="text-right">Стійкість</TableHead>
            <TableHead className="text-right">Пошуки</TableHead>
            <TableHead className="text-right">Ліцензія</TableHead>
            <TableHead>Рішення</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {ranking.rows.map((row) => {
            const licensed = row.choice === "licensed"
            return (
              <TableRow key={String(row.candidate_id)}>
                <TableCell className="text-right tabular-nums">{row.rank_topsis}</TableCell>
                <TableCell className="max-w-72 whitespace-normal">
                  <div className="font-medium">{row.title}</div>
                  <div className="text-xs text-muted-foreground">{row.authors}</div>
                </TableCell>
                <TableCell className="whitespace-normal">{label("genre", row.genre)}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatDecimal(numberOf(row.topsis), 3)}
                </TableCell>
                <TableCell className="text-right tabular-nums">{row.rank_saw}</TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatValue(numberOf(row.stability), "ratio")}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatValue(numberOf(row.demand_searches), "count")}
                </TableCell>
                <TableCell className="text-right whitespace-nowrap tabular-nums">
                  {formatValue(numberOf(row.license_cost), "UAH")}
                </TableCell>
                <TableCell>
                  <Badge variant={licensed ? "default" : "outline"}>
                    {label("content_choice", row.choice)}
                  </Badge>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}
