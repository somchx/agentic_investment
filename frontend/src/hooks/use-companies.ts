import { useQuery } from "@tanstack/react-query"
import { fetchCompanies } from "@/api/companies"
import { queryKeys } from "@/hooks/query-keys"

export function useCompanies() {
  return useQuery({
    queryKey: queryKeys.companies,
    queryFn: fetchCompanies,
    staleTime: 5 * 60 * 1000,
  })
}
