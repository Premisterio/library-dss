import { Spinner } from "@/components/ui/spinner"

/** A whole page that is still loading. */
export function PageSpinner() {
  return (
    <div className="flex min-h-svh items-center justify-center">
      <Spinner className="size-6" />
    </div>
  )
}
