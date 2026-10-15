import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { useQueryClient } from "@tanstack/react-query"
import * as authApi from "@/api/auth"
import { registerUnauthorizedHandler } from "@/api/client"
import { clearToken, getToken, setToken } from "@/lib/auth-storage"
import type { User } from "@/types"

interface AuthContextValue {
  user: User | null
  token: string | null
  status: "loading" | "authenticated" | "unauthenticated"
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, fullName: string) => Promise<void>
  updateProfile: (fullName: string, email: string) => Promise<void>
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setTokenState] = useState<string | null>(() => getToken())
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthContextValue["status"]>(
    getToken() ? "loading" : "unauthenticated",
  )

  const logout = useCallback(() => {
    clearToken()
    setTokenState(null)
    setUser(null)
    setStatus("unauthenticated")
    queryClient.clear()
  }, [queryClient])

  useEffect(() => {
    registerUnauthorizedHandler(logout)
  }, [logout])

  useEffect(() => {
    let cancelled = false
    if (!token) {
      setStatus("unauthenticated")
      return
    }
    authApi
      .fetchMe()
      .then((me) => {
        if (!cancelled) {
          setUser(me)
          setStatus("authenticated")
        }
      })
      .catch(() => {
        if (!cancelled) {
          clearToken()
          setTokenState(null)
          setUser(null)
          setStatus("unauthenticated")
        }
      })
    return () => {
      cancelled = true
    }
    // Only re-run when the token itself changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password })
    setToken(res.access_token)
    setTokenState(res.access_token)
    setUser(res.user)
    setStatus("authenticated")
  }, [])

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    const res = await authApi.register({ email, password, full_name: fullName })
    setToken(res.access_token)
    setTokenState(res.access_token)
    setUser(res.user)
    setStatus("authenticated")
  }, [])

  const updateProfile = useCallback(async (fullName: string, email: string) => {
    setUser(await authApi.updateProfile({ full_name: fullName, email }))
  }, [])

  const changePassword = useCallback(async (currentPassword: string, newPassword: string) => {
    const res = await authApi.changePassword(currentPassword, newPassword)
    setToken(res.access_token)
    setTokenState(res.access_token)
    setUser(res.user)
  }, [])

  const value = useMemo(
    () => ({ user, token, status, login, register, logout, updateProfile, changePassword }),
    [user, token, status, login, register, logout, updateProfile, changePassword],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider")
  return ctx
}
