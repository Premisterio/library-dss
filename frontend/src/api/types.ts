/** The API's models under short names; everything derives from the generated schema. */
import type { paths, Schemas } from "@library-dss/api-client"

export type { Schemas }

export type Problem = Schemas["Problem"]
export type TokenOut = Schemas["TokenOut"]
export type Analyst = Schemas["AnalystOut"]

export type Dataset = Schemas["DatasetOut"]
export type DatasetStatus = Dataset["status"]
export type Capability = Dataset["capabilities"][number]
export type TaskError = Schemas["TaskError"]
export type UploadAccepted = Schemas["UploadAccepted"]

export type Job = Schemas["JobOut"]

export type Section = Schemas["SectionOut"]
export type SectionKey = Section["key"]
export type Sections = Partial<Record<SectionKey, Section>>
export type Kpi = Schemas["KpiOut"]
export type Note = Schemas["NoteOut"]
export type Chart = Schemas["ChartOut"]
export type Dimension = Schemas["DimensionOut"]
export type Measure = Schemas["MeasureOut"]
export type Unit = Measure["unit"]
export type Row = Chart["rows"][number]
export type Cell = Row[string]

export type Report = Schemas["ReportOut"]
type ExportQuery = NonNullable<
  paths["/api/v1/reports/{report_id}/export"]["get"]["parameters"]["query"]
>
export type ExportFormat = NonNullable<ExportQuery["format"]>
