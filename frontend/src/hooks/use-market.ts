import { useQuery } from "@tanstack/react-query"
import { fetchHistory, fetchQuote, fetchQuotes } from "@/api/market"
import { queryKeys } from "@/hooks/query-keys"
import type { HistoryRange } from "@/types"

// Polled at roughly the same cadence as the backend's own quote cache TTL
// (30s, see market_data.py) -- "real-time" here means refreshed every
// ~30s while the page is open, not a streaming feed. Free, no cost
// confirmation needed (unlike the LLM-backed endpoints): this is a plain
// price lookup, not a paid API call.
const QUOTE_REFETCH_INTERVAL_MS = 30_000

export function useQuote(ticker: string) {
  return useQuery({
    queryKey: queryKeys.quote(ticker),
    queryFn: () => fetchQuote(ticker),
    enabled: Boolean(ticker),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => query.state.error || !query.state.data || Object.keys(query.state.data).length === 0
      ? 5 * 60_000 : QUOTE_REFETCH_INTERVAL_MS,
    staleTime: QUOTE_REFETCH_INTERVAL_MS,
  })
}

export function useQuotes(tickers: string[]) {
  return useQuery({
    queryKey: queryKeys.quotes(tickers),
    queryFn: () => fetchQuotes(tickers),
    enabled: tickers.length > 0,
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (query) => query.state.error || !query.state.data || Object.keys(query.state.data).length === 0
      ? 5 * 60_000 : QUOTE_REFETCH_INTERVAL_MS,
    staleTime: QUOTE_REFETCH_INTERVAL_MS,
  })
}

// Historical series changes slowly (today's partial bar aside) -- no
// polling, just a normal cached fetch per (ticker, range).
export function useHistory(ticker: string, range: HistoryRange = "3mo") {
  return useQuery({
    queryKey: queryKeys.history(ticker, range),
    queryFn: () => fetchHistory(ticker, range),
    enabled: Boolean(ticker),
    staleTime: 5 * 60_000,
    retry: false,
    refetchOnWindowFocus: false,
  })
}
