import type { TaskError } from "@/api/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { messageFor } from "@/lib/messages"

/** Why a job failed, with the individual problems it found (in a file, say). */
export function ProblemList({ error }: { error: TaskError }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>{messageFor(error.code, error.detail)}</AlertTitle>
      {error.errors && error.errors.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-4">
            {error.errors.map((problem) => (
              <li key={problem}>
                <code className="text-xs">{problem}</code>
              </li>
            ))}
          </ul>
        </AlertDescription>
      )}
    </Alert>
  )
}
