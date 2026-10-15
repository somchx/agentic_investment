import { apiClient } from "@/api/client"
import type { AuthResponse, User } from "@/types"

export interface Credentials {
  email: string
  password: string
}

export async function register(payload: Credentials & { full_name: string }): Promise<AuthResponse> {
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

export async function updateProfile(payload: { full_name: string; email: string }): Promise<User> {
  const { data } = await apiClient.patch<User>("/auth/me", payload)
  return data
}

export async function changePassword(current_password: string, new_password: string): Promise<AuthResponse> {
  const { data } = await apiClient.post<AuthResponse>("/auth/change-password", { current_password, new_password })
  return data
}
