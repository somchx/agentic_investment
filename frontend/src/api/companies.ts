import { apiClient } from "@/api/client"
import type { Company } from "@/types"

export async function fetchCompanies(): Promise<Company[]> {
  const { data } = await apiClient.get<Company[]>("/companies")
  return data
}
