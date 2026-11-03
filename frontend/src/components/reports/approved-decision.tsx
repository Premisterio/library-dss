import { Link } from "react-router"

import type { Report } from "@/api/types"
import { paths } from "@/app/paths"
import { approvedText } from "@/lib/steps"

/** A decision already approved on the page's question, with the way to it among the reports. */
export function ApprovedDecision({ report }: { report: Report }) {
  return (
    <p className="text-sm text-muted-foreground">
      {approvedText(report)} ·{" "}
      <Link
        to={paths.reports(report.dataset_id)}
        className="underline underline-offset-2 hover:text-foreground"
      >
        До звітів
      </Link>
    </p>
  )
}
