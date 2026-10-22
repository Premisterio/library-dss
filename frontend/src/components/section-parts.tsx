import { InfoIcon } from "lucide-react"

import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import type { Schemas } from "@/lib/api"
import { useLabel } from "@/lib/enums"
import { formatValue, windowText } from "@/lib/format"
import type { Dataset } from "@/lib/queries"

type Kpi = Schemas["KpiOut"]
type Note = Schemas["NoteOut"]

export function KpiGrid({ kpis }: { kpis: Kpi[] }) {
  const label = useLabel()
  if (kpis.length === 0) return null
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <Card key={kpi.key} size="sm">
          <CardHeader>
            <CardDescription>{label("metric", kpi.key)}</CardDescription>
            <CardTitle className="text-2xl tabular-nums">
              {formatValue(kpi.value, kpi.unit)}
            </CardTitle>
          </CardHeader>
          <CardFooter className="text-xs text-muted-foreground">
            {kpi.value === null
              ? "немає даних у датасеті"
              : windowText(kpi.window_days) || "станом на дату зрізу"}
          </CardFooter>
        </Card>
      ))}
    </div>
  )
}

export function Notes({ notes }: { notes: Note[] }) {
  if (notes.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      {notes.map((note) => (
        <Alert key={note.code}>
          <InfoIcon />
          <AlertDescription>{note.message_uk}</AlertDescription>
        </Alert>
      ))}
    </div>
  )
}

const STATUS_VARIANT = {
  pending: "outline",
  importing: "secondary",
  ready: "default",
  failed: "destructive",
} as const

export function DatasetStatus({ status }: { status: Dataset["status"] }) {
  const label = useLabel()
  return <Badge variant={STATUS_VARIANT[status]}>{label("dataset_status", status)}</Badge>
}

export function Capabilities({ capabilities }: { capabilities: Dataset["capabilities"] }) {
  const label = useLabel()
  return (
    <div className="flex flex-wrap gap-1">
      {capabilities.map((capability) => (
        <Badge key={capability} variant="outline">
          {label("capability", capability)}
        </Badge>
      ))}
    </div>
  )
}
