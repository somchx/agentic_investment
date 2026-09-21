import { apiClient } from "@/api/client"
import type { CreateProfilePayload, InvestorProfile } from "@/types"

export async function fetchProfiles(): Promise<InvestorProfile[]> {
  const { data } = await apiClient.get<InvestorProfile[]>("/profiles")
  return data
}

export async function createProfile(payload: CreateProfilePayload): Promise<InvestorProfile> {
  const { data } = await apiClient.post<InvestorProfile>("/profiles", payload)
  return data
}

export async function deleteProfile(id: string): Promise<void> {
  await apiClient.delete(`/profiles/${encodeURIComponent(id)}`)
}
