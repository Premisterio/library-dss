import { useNavigate } from "react-router"
import { toast } from "sonner"

import { useApprovePlan } from "@/api/retention"
import type { ChurnRun, PlanIn } from "@/api/types"
import { paths } from "@/app/paths"
import { ApproveDialog } from "@/components/common/approve-dialog"
import { formatValue } from "@/lib/format"

/** Freeze the plan on screen as a decision, kept among the dataset's reports. */
export function ApprovePlan({ run, plan }: { run: ChurnRun; plan: PlanIn }) {
  const approve = useApprovePlan(run)
  const navigate = useNavigate()
  return (
    <ApproveDialog
      label="Затвердити план"
      title="Затвердити план?"
      description="План збережеться як рішення серед звітів датасету разом з умовами, за якими його складено. Його можна завантажити в PDF, Excel, CSV чи JSON."
      defaultName={`План утримання, бюджет ${formatValue(plan.budget, "UAH")}`}
      onApprove={async (title) => {
        const report = await approve.mutateAsync({ title, plan })
        toast.success(`Рішення «${report.title}» збережено`, {
          action: {
            label: "До звітів",
            onClick: () => void navigate(paths.reports(run.dataset_id)),
          },
        })
      }}
    />
  )
}
