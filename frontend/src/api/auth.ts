import { apiClient } from "@/api/client"
import type { AuthResponse, User } from "@/types"

export interface Credentials {
  email: string
  password: string
}

export async function register(payload: Credentials): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/register", payload)
  return data
}

export async function login(payload: Credentials): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/login", payload)
  return data
}

export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/auth/me")
  return data
}
