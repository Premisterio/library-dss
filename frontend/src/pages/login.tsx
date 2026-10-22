import { LibraryIcon } from "lucide-react"
import type { FormEvent } from "react"
import { Navigate, useLocation } from "react-router"

import { useAuth, useLogin } from "@/api/auth"
import { errorMessage } from "@/api/problem"
import { paths } from "@/app/paths"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { formText } from "@/lib/forms"

/** Where to go after signing in: the page that asked for it, or the dataset list. */
function redirectTarget(state: unknown): string {
  if (
    typeof state === "object" &&
    state !== null &&
    "from" in state &&
    typeof state.from === "string"
  ) {
    return state.from
  }
  return paths.datasets
}

export function LoginPage() {
  const { ready, signedIn } = useAuth()
  const login = useLogin()
  const location = useLocation()
  const from = redirectTarget(location.state)

  // Also the way out after a successful sign-in.
  if (ready && signedIn) return <Navigate to={from} replace />

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    // A password is used as typed: spaces may be part of it.
    login.mutate({
      email: formText(form, "email"),
      password: formText(form, "password", { trim: false }),
    })
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
          <form onSubmit={submit}>
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
              {login.isError && <FieldError>{errorMessage(login.error)}</FieldError>}
              <Button type="submit" disabled={login.isPending || !ready}>
                {login.isPending && <Spinner />}
                Увійти
              </Button>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
