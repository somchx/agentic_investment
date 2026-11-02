import { apiClient } from "@/api/client"
import type { HistoryRange, PricePoint, Quote } from "@/types"

export async function fetchQuote(ticker: string): Promise<Quote> {
  const { data } = await apiClient.get<Quote>(`/market/quote/${encodeURIComponent(ticker)}`)
  return data
}

export async function fetchHistory(ticker: string, range: HistoryRange = "3mo"): Promise<PricePoint[]> {
  const { data } = await apiClient.get<PricePoint[]>(`/market/history/${encodeURIComponent(ticker)}`, {
    params: { range },
  })
  return data
}

// Best-effort batch -- tickers the data source has no quote for are simply
// absent from the returned map rather than failing the whole request.
export async function fetchQuotes(tickers: string[]): Promise<Record<string, Quote>> {
  if (tickers.length === 0) return {}
  const { data } = await apiClient.get<Record<string, Quote>>("/market/quotes", {
    params: { tickers: tickers.join(",") },
  })
  return data
}
