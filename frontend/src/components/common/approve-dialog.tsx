import { CheckIcon } from "lucide-react"
import { useState, type FormEvent, type ReactNode } from "react"

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
import { formText } from "@/lib/forms"

/**
 * Names a decision and approves it. The dialog closes when `onApprove` resolves and stays open
 * when it fails (the mutation cache shows the error).
 */
export function ApproveDialog({
  label,
  title,
  description,
  defaultName,
  disabled = false,
  onApprove,
}: {
  label: string
  title: string
  description: ReactNode
  defaultName: string
  disabled?: boolean
  onApprove: (name: string) => Promise<unknown>
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = formText(new FormData(event.currentTarget), "title")
    if (!name) return
    setBusy(true)
    try {
      await onApprove(name)
      setOpen(false)
    } catch {
      // keep the dialog open so the approval can be retried
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button disabled={disabled}>
          <CheckIcon />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <Field>
            <FieldLabel htmlFor="decision-title">Назва</FieldLabel>
            <Input
              id="decision-title"
              name="title"
              required
              maxLength={200}
              defaultValue={defaultName}
            />
          </Field>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Скасувати
              </Button>
            </DialogClose>
            <Button type="submit" disabled={busy}>
              {busy && <Spinner />}
              Затвердити
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
