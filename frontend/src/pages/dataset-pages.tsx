import { useMutation, useQueryClient } from "@tanstack/react-query"
import { DownloadIcon, FileTextIcon, Trash2Icon } from "lucide-react"
import { useState, type FormEvent, type ReactNode } from "react"
import { Link, Navigate, useNavigate, useParams } from "react-router"
import { toast } from "sonner"

import { Capabilities, DatasetStatus, KpiGrid, Notes } from "@/components/section-parts"
import { TidyChart } from "@/components/tidy-chart"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { Field, FieldGroup, FieldLabel, FieldLegend, FieldSet } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, expectOk, unwrap } from "@/lib/api"
import { downloadFile } from "@/lib/download"
import { useLabel } from "@/lib/enums"
import { formatDateTime, formatDay } from "@/lib/format"
import { formText } from "@/lib/forms"
import { errorMessage } from "@/lib/problem"
import {
  ANALYTICS_TABS,
  keys,
  useAnalytics,
  useDataset,
  useReports,
  type Dataset,
  type Report,
  type Section,
  type SectionKey,
} from "@/lib/queries"

function useDatasetId(): number {
  const { datasetId } = useParams()
  return Number(datasetId)
}

/** Loads the dataset; shows why there is nothing to show yet, or renders the page. */
function WithReadyDataset({ children }: { children: (dataset: Dataset) => ReactNode }) {
  const id = useDatasetId()
  const dataset = useDataset(id)
  if (dataset.isPending) return <Skeleton className="h-40 w-full" />
  if (dataset.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{errorMessage(dataset.error)}</AlertTitle>
        <AlertDescription>
          <Link to="/datasets" className="underline">
            До списку датасетів
          </Link>
        </AlertDescription>
      </Alert>
    )
  }
  if (dataset.data.status !== "ready") {
    return (
      <Alert>
        <AlertTitle>
          Датасет «{dataset.data.name}»: <DatasetStatus status={dataset.data.status} />
        </AlertTitle>
        <AlertDescription>Аналітика з'явиться, щойно імпорт завершиться.</AlertDescription>
      </Alert>
    )
  }
  return children(dataset.data)
}

function DatasetHeader({ dataset }: { dataset: Dataset }) {
  return (
    <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{dataset.name}</h2>
        <p className="text-sm text-muted-foreground">
          Станом на {dataset.as_of ? formatDay(dataset.as_of) : "—"} · {dataset.timezone}
        </p>
      </div>
      <Capabilities capabilities={dataset.capabilities} />
    </div>
  )
}

function SectionBody({ section, skipKpis = false }: { section: Section; skipKpis?: boolean }) {
  return (
    <div className="flex flex-col gap-4">
      <Notes notes={section.notes} />
      {!skipKpis && <KpiGrid kpis={section.kpis} />}
      <div className="grid gap-4 2xl:grid-cols-2">
        {section.charts.map((chart) => (
          <TidyChart key={chart.key} chart={chart} />
        ))}
      </div>
    </div>
  )
}

function MaybeSection({ section }: { section: Section | undefined }) {
  if (!section) {
    return (
      <Alert>
        <AlertTitle>Цієї секції немає в аналітиці датасету.</AlertTitle>
      </Alert>
    )
  }
  return <SectionBody section={section} />
}

function SectionLoader({
  datasetId,
  children,
}: {
  datasetId: number
  children: (sections: Partial<Record<SectionKey, Section>>) => ReactNode
}) {
  const analytics = useAnalytics(datasetId)
  if (analytics.isPending) return <Skeleton className="h-64 w-full" />
  if (analytics.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{errorMessage(analytics.error)}</AlertTitle>
      </Alert>
    )
  }
  return children(analytics.data)
}

export function OverviewPage() {
  return (
    <WithReadyDataset>
      {(dataset) => (
        <>
          <DatasetHeader dataset={dataset} />
          <SectionLoader datasetId={dataset.id}>
            {(sections) => <MaybeSection section={sections.overview} />}
          </SectionLoader>
        </>
      )}
    </WithReadyDataset>
  )
}

export function AnalyticsPage() {
  const { section } = useParams()
  const navigate = useNavigate()
  const label = useLabel()
  const id = useDatasetId()
  const active = ANALYTICS_TABS.find((key) => key === section)
  if (!active) return <Navigate to={`/d/${id}/analytics/${ANALYTICS_TABS[0]}`} replace />
  return (
    <WithReadyDataset>
      {(dataset) => (
        <>
          <DatasetHeader dataset={dataset} />
          <Tabs
            value={active}
            onValueChange={(value) => void navigate(`/d/${dataset.id}/analytics/${value}`)}
          >
            <TabsList className="flex-wrap">
              {ANALYTICS_TABS.map((key) => (
                <TabsTrigger key={key} value={key}>
                  {label("analytics_section", key)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <SectionLoader datasetId={dataset.id}>
            {(sections) => <MaybeSection section={sections[active]} />}
          </SectionLoader>
        </>
      )}
    </WithReadyDataset>
  )
}

const FORMATS = [
  { value: "pdf", label: "PDF" },
  { value: "xlsx", label: "Excel (XLSX)" },
  { value: "csv", label: "CSV (zip)" },
  { value: "json", label: "JSON" },
] as const

function Downloads({ report }: { report: Report }) {
  const [busy, setBusy] = useState(false)
  async function download(format: (typeof FORMATS)[number]["value"]) {
    setBusy(true)
    try {
      await downloadFile(
        `/api/v1/reports/${report.id}/export?format=${format}`,
        `report-${report.id}.${format === "csv" ? "zip" : format}`
      )
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={busy}>
          {busy ? <Spinner /> : <DownloadIcon />}
          Завантажити
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {FORMATS.map((format) => (
          <DropdownMenuItem key={format.value} onSelect={() => void download(format.value)}>
            {format.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function CreateReport({ dataset }: { dataset: Dataset }) {
  const label = useLabel()
  const queryClient = useQueryClient()
  const all: SectionKey[] = ["overview", ...ANALYTICS_TABS]
  const [chosen, setChosen] = useState<SectionKey[]>(all)
  const create = useMutation({
    mutationFn: async (title: string) =>
      unwrap(
        await api.POST("/api/v1/reports", {
          body: { dataset_id: dataset.id, title, sections: chosen },
        })
      ),
    onSuccess: (report) => {
      toast.success(`Звіт «${report.title}» створено`)
      void queryClient.invalidateQueries({ queryKey: keys.reports(dataset.id) })
    },
    onError: (error) => toast.error(errorMessage(error)),
  })
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = formText(new FormData(event.currentTarget), "title")
    if (title && chosen.length > 0) create.mutate(title)
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Новий звіт</CardTitle>
        <CardDescription>
          Звіт фіксує вибрані секції аналітики на момент створення; його можна завантажити в PDF,
          Excel, CSV чи JSON.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="title">Назва</FieldLabel>
              <Input
                id="title"
                name="title"
                required
                maxLength={200}
                defaultValue={`Звіт: ${dataset.name}`}
              />
            </Field>
            <FieldSet>
              <FieldLegend variant="label">Секції</FieldLegend>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {all.map((key) => (
                  <Field key={key} orientation="horizontal">
                    <Checkbox
                      id={`section-${key}`}
                      checked={chosen.includes(key)}
                      onCheckedChange={(checked) =>
                        setChosen((current) =>
                          checked
                            ? all.filter((k) => k === key || current.includes(k))
                            : current.filter((k) => k !== key)
                        )
                      }
                    />
                    <FieldLabel htmlFor={`section-${key}`} className="font-normal">
                      {label("analytics_section", key)}
                    </FieldLabel>
                  </Field>
                ))}
              </div>
            </FieldSet>
            <Button
              type="submit"
              className="self-start"
              disabled={create.isPending || chosen.length === 0}
            >
              {create.isPending ? <Spinner /> : <FileTextIcon />}
              Створити звіт
            </Button>
          </FieldGroup>
        </form>
      </CardContent>
    </Card>
  )
}

function DeleteReport({ report, datasetId }: { report: Report; datasetId: number }) {
  const queryClient = useQueryClient()
  const remove = useMutation({
    mutationFn: async () =>
      expectOk(
        await api.DELETE("/api/v1/reports/{report_id}", {
          params: { path: { report_id: report.id } },
        })
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: keys.reports(datasetId) }),
    onError: (error) => toast.error(errorMessage(error)),
  })
  return (
    <Button
      variant="ghost"
      size="icon"
      title="Видалити звіт"
      disabled={remove.isPending}
      onClick={() => remove.mutate()}
    >
      <Trash2Icon />
    </Button>
  )
}

function ReportList({ datasetId }: { datasetId: number }) {
  const label = useLabel()
  const reports = useReports(datasetId)
  if (reports.isPending) return <Skeleton className="h-24 w-full" />
  if (reports.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>{errorMessage(reports.error)}</AlertTitle>
      </Alert>
    )
  }
  if (reports.data.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <FileTextIcon />
          </EmptyMedia>
          <EmptyTitle>Звітів ще немає</EmptyTitle>
          <EmptyDescription>Створіть перший звіт вище.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Назва</TableHead>
          <TableHead>Секції</TableHead>
          <TableHead>Створено</TableHead>
          <TableHead className="text-right">Дії</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {reports.data.map((report) => (
          <TableRow key={report.id}>
            <TableCell className="font-medium">{report.title}</TableCell>
            <TableCell className="max-w-md whitespace-normal text-muted-foreground">
              {report.sections.map((key) => label("analytics_section", key)).join(", ")}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatDateTime(report.created_at)}
            </TableCell>
            <TableCell>
              <div className="flex justify-end gap-1">
                <Downloads report={report} />
                <DeleteReport report={report} datasetId={datasetId} />
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

export function ReportsPage() {
  return (
    <WithReadyDataset>
      {(dataset) => (
        <>
          <DatasetHeader dataset={dataset} />
          <CreateReport dataset={dataset} />
          <Card>
            <CardHeader>
              <CardTitle>Звіти датасету</CardTitle>
              <CardDescription>Найновіші зверху.</CardDescription>
            </CardHeader>
            <CardContent>
              <ReportList datasetId={dataset.id} />
            </CardContent>
          </Card>
        </>
      )}
    </WithReadyDataset>
  )
}
