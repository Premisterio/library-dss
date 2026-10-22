import { useQuery } from "@tanstack/react-query"
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react"

import { api, unwrap, type Schemas } from "@/lib/api"
import { queryClient } from "@/lib/query-client"
import { clearSession, isSignedIn, refresh, setSession, subscribe } from "@/lib/session"

type Analyst = Schemas["AnalystOut"]

type Auth = {
  /** False until the first silent sign-in attempt (refresh cookie) has finished. */
  ready: boolean
  signedIn: boolean
  analyst: Analyst | undefined
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<Auth | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const signedIn = useSyncExternalStore(subscribe, isSignedIn)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    void refresh().finally(() => setReady(true))
  }, [])

  const me = useQuery({
    queryKey: ["me"],
    queryFn: async () => unwrap(await api.GET("/api/v1/auth/me")),
    enabled: signedIn,
  })

  const login = useCallback(async (email: string, password: string) => {
    const tokens = unwrap(
      await api.POST("/api/v1/auth/login", {
        body: { email, password, include_refresh_token: false },
      })
    )
    setSession(tokens.access_token, tokens.expires_in)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.POST("/api/v1/auth/logout")
    } finally {
      clearSession()
      queryClient.clear()
    }
  }, [])

  const analyst = me.data
  const value = useMemo(
    () => ({ ready, signedIn, analyst, login, logout }),
    [ready, signedIn, analyst, login, logout]
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): Auth {
  const auth = useContext(AuthContext)
  if (!auth) throw new Error("useAuth must be used inside AuthProvider")
  return auth
}
