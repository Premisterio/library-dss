import { LibraryIcon } from "lucide-react"
import { useState, type FormEvent } from "react"
import { Navigate, useLocation, useNavigate } from "react-router"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { useAuth } from "@/lib/auth"
import { formText } from "@/lib/forms"
import { errorMessage } from "@/lib/problem"

function redirectTarget(state: unknown): string {
  if (
    typeof state === "object" &&
    state !== null &&
    "from" in state &&
    typeof state.from === "string"
  ) {
    return state.from
  }
  return "/datasets"
}

export function LoginPage() {
  const { ready, signedIn, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = redirectTarget(location.state)
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)

  if (ready && signedIn) return <Navigate to={from} replace />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setBusy(true)
    setError(undefined)
    try {
      await login(formText(form, "email"), formText(form, "password"))
      void navigate(from, { replace: true })
    } catch (caught) {
      setError(errorMessage(caught))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <LibraryIcon className="size-5" />
          </div>
          <CardTitle className="text-xl">СППР онлайн-бібліотеки</CardTitle>
          <CardDescription>Увійдіть, щоб працювати з датасетами й аналітикою.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={(event) => void submit(event)}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">E-mail</FieldLabel>
                <Input id="email" name="email" type="email" autoComplete="username" required />
              </Field>
              <Field>
                <FieldLabel htmlFor="password">Пароль</FieldLabel>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </Field>
              {error && <FieldError>{error}</FieldError>}
              <Button type="submit" disabled={busy || !ready}>
                {busy && <Spinner />}
                Увійти
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}

/** Routes behind sign-in: waits for the silent sign-in, then shows the page or the login form. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { ready, signedIn } = useAuth()
  const location = useLocation()
  if (!ready) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (!signedIn) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return children
}
