import { useMutation } from "@tanstack/react-query"
import { useQuery } from "@tanstack/react-query"
import { askAgent, askAgentPortfolio, fetchReport, personalize } from "@/api/report"
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

export function usePersonalize(ticker: string) {
  return useMutation({
    mutationFn: (profileId: string) => personalize(ticker, profileId),
  })
}
