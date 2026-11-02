import { useQuery } from "@tanstack/react-query"
import { fetchHistory } from "@/api/market"
import type { HistoryRange, PricePoint } from "@/types"

// Aggregated portfolio value over time: for each date in range, sum
// (quantity held today x that ticker's close on that date) across every
// held ticker. This answers "what would today's holdings have been worth
// on past dates" -- a common, understood simplification (it doesn't
// replay when shares were actually bought/sold), not a claim of exact
// historical portfolio value. No backend endpoint for this; it's a plain
// client-side aggregation over each ticker's own /market/history series.
export function usePortfolioHistory(quantityByTicker: Record<string, number>, range: HistoryRange = "3mo") {
  const tickers = Object.keys(quantityByTicker).sort()
  return useQuery({
    queryKey: ["portfolio-history", tickers, range],
    queryFn: async (): Promise<PricePoint[]> => {
      const seriesList = await Promise.all(tickers.map((t) => fetchHistory(t, range)))
      const byDate = new Map<string, number>()
      seriesList.forEach((series, i) => {
        const qty = quantityByTicker[tickers[i]]
        series.forEach((point) => {
          byDate.set(point.date, (byDate.get(point.date) ?? 0) + qty * point.close)
        })
      })
      return Array.from(byDate.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, close]) => ({ date, close }))
    },
    enabled: tickers.length > 0,
    staleTime: 5 * 60_000,
  })
}
