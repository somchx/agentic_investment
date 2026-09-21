import axios, { AxiosError } from "axios"
import { clearToken, getToken } from "@/lib/auth-storage"
import type { ApiErrorBody } from "@/types"

export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000"

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api`,
})

// Attach the bearer token to every request except register/login, which
// don't need it (and won't have a token to send yet on first login anyway).
const PUBLIC_PATHS = ["/auth/register", "/auth/login"]

apiClient.interceptors.request.use((config) => {
  const isPublic = PUBLIC_PATHS.some((p) => config.url?.includes(p))
  if (!isPublic) {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// A single spot to react to global auth failures. `onUnauthorized` is wired
// up from the app shell so we can redirect to /login on a 401.
let onUnauthorized: (() => void) | null = null
export function registerUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (error.response?.status === 401) {
      clearToken()
      onUnauthorized?.()
    }
    return Promise.reject(error)
  },
)

export function getApiErrorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ApiErrorBody | undefined
    if (typeof data?.detail === "string") return data.detail
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail.map((d) => d.msg).join(", ")
    }
    if (data?.message) return data.message
    if (error.message) return error.message
  }
  return fallback
}
