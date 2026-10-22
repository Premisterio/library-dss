import { Card, CardContent } from "@/components/ui/card"

/**
 * One headline number: label, value and what it covers. The value keeps proportional figures;
 * tabular figures are only for columns that must align.
 */
export function StatTile({
  label,
  value,
  footnote,
}: {
  label: string
  value: string
  footnote: string
}) {
  return (
    <Card size="sm">
      <CardContent className="flex flex-col gap-1">
        <p className="text-[13px] text-muted-foreground">{label}</p>
        <p className="text-[26px] leading-8 font-semibold">{value}</p>
        <p className="text-xs text-muted-foreground">{footnote}</p>
      </CardContent>
    </Card>
  )
}
