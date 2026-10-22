import { InfoIcon } from "lucide-react"

import type { Note } from "@/api/types"
import { Alert, AlertDescription } from "@/components/ui/alert"

/** What the reader should know about a section's numbers (missing data, caveats). */
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
