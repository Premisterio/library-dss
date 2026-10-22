import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react"

import { api } from "@/api/client"
import { keys } from "@/api/keys"
import { unwrap } from "@/api/problem"
import { clearSession, isSignedIn, onSignOut, refresh, setSession, subscribe } from "@/api/session"
import type { Analyst } from "@/api/types"

type Auth = {
  /** False until the first silent sign-in attempt (refresh cookie) has finished. */
  ready: boolean
  signedIn: boolean
  analyst: Analyst | undefined
}

const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const signedIn = useSyncExternalStore(subscribe, isSignedIn)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    void refresh().finally(() => setReady(true))
  }, [])

  // Whatever ends a session, the next analyst must not see the previous one's cached data.
  useEffect(() => onSignOut(() => queryClient.clear()), [queryClient])

  const me = useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/me")),
    enabled: signedIn,
  })

  const analyst = me.data
  const value = useMemo(() => ({ ready, signedIn, analyst }), [ready, signedIn, analyst])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error("useAuth must be used inside AuthProvider")
  return auth
}

/** Sign in; the form shows the error itself. */
export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const tokens = unwrap(
        await api.POST("/api/v1/auth/login", {
          body: { email, password, include_refresh_token: false },
        })
      )
      queryClient.clear()
      setSession(tokens.access_token, tokens.expires_in)
    },
    meta: { silent: true },
  })
}

/** Sign out here and revoke the refresh cookie; the session ends even if the call fails. */
export function useLogout() {
  return useMutation({
    mutationFn: async () => {
      try {
        await api.POST("/api/v1/auth/logout")
      } finally {
        clearSession()
      }
    },
    meta: { silent: true },
  })
}
