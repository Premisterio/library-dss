import type { ReactNode } from "react"

import { errorMessage } from "@/api/problem"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

/** A failed request or action, in the user's words; `children` add details or a way out. */
export function ErrorAlert({ error, children }: { error: unknown; children?: ReactNode }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{errorMessage(error)}</AlertTitle>
      {children && <AlertDescription>{children}</AlertDescription>}
    </Alert>
  )
}
