import { CheckIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router"
import { toast } from "sonner"

import { useApprovePlan } from "@/api/retention"
import type { ChurnRun, PlanIn } from "@/api/types"
import { paths } from "@/app/paths"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Field, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { formatValue } from "@/lib/format"
import { formText } from "@/lib/forms"

/** Freeze the plan on screen as a decision, kept among the dataset's reports. */
export function ApprovePlan({ run, plan }: { run: ChurnRun; plan: PlanIn }) {
  const approve = useApprovePlan(run)
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = formText(new FormData(event.currentTarget), "title")
    if (!title) return
    approve.mutate(
      { title, plan },
      {
        onSuccess: (report) => {
          setOpen(false)
          toast.success(`Рішення «${report.title}» збережено`, {
            action: {
              label: "До звітів",
              onClick: () => void navigate(paths.reports(run.dataset_id)),
            },
          })
        },
      }
    )
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <CheckIcon />
          Затвердити план
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Затвердити план?</DialogTitle>
            <DialogDescription>
              План збережеться як рішення серед звітів датасету разом з умовами, за якими його
              складено. Його можна завантажити в PDF, Excel, CSV чи JSON.
            </DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="plan-title">Назва</FieldLabel>
            <Input
              id="plan-title"
              name="title"
              required
              maxLength={200}
              defaultValue={`План утримання, бюджет ${formatValue(plan.budget, "UAH")}`}
            />
          </Field>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Скасувати
              </Button>
            </DialogClose>
            <Button type="submit" disabled={approve.isPending}>
              {approve.isPending && <Spinner />}
              Затвердити
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
