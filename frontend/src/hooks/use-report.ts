import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { askAgent, askAgentPortfolio, fetchLatestInvestigation, fetchReport, investigateCompany, personalize } from "@/api/report"
import { queryKeys } from "@/hooks/query-keys"
import type { ChatTurn } from "@/types"

export function useReport(ticker: string) {
  return useQuery({
    queryKey: queryKeys.report(ticker),
    queryFn: () => fetchReport(ticker),
    enabled: Boolean(ticker),
  })
}

// Money-costing mutations: never fire from a useEffect/on-mount. Only wire
// these to a button behind an explicit confirmation dialog.
export function useAskAgent(ticker: string) {
  return useMutation({
    mutationFn: ({ question, history }: { question: string; history?: ChatTurn[] }) =>
      askAgent(ticker, question, history),
  })
}

export function useAskAgentPortfolio() {
  return useMutation({
    mutationFn: ({ question, history }: { question: string; history?: ChatTurn[] }) =>
      askAgentPortfolio(question, history),
  })
}

// Free read of the stored AI Summary -- safe to load when the modal opens.
export function useLatestInvestigation(ticker: string) {
  return useQuery({
    queryKey: queryKeys.aiSummary(ticker),
    queryFn: () => fetchLatestInvestigation(ticker),
    enabled: Boolean(ticker),
  })
}

export function useInvestigate(ticker: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => investigateCompany(ticker),
    // The server stores the new summary; show it straight away without a refetch.
    onSuccess: (result) => queryClient.setQueryData(queryKeys.aiSummary(ticker), result),
  })
}

export function usePersonalize(ticker: string) {
  return useMutation({
    mutationFn: (profileId: string) => personalize(ticker, profileId),
  })
}
