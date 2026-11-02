import { useEffect, useState } from "react"
import { useIsFetching, useQueryClient, type Query } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useTranslation } from "@/i18n/context"
import { cn } from "@/lib/utils"

// The queries the dashboard is built from: prices, holdings, watchlist.
const DASHBOARD_ROOTS = new Set(["quotes", "quote", "portfolio", "positions", "companies"])
const isDashboardQuery = (query: Query) => DASHBOARD_ROOTS.has(String(query.queryKey[0]))

// Same bands as the log portal's freshness badge: <= 5 min live, <= 30 min delayed, else stale.
function freshnessOf(ageMinutes: number) {
  if (ageMinutes <= 5) return { key: "freshness_live", variant: "supported" as const }
  if (ageMinutes <= 30) return { key: "freshness_delayed", variant: "weakened" as const }
  return { key: "freshness_stale", variant: "broken" as const }
}

/** "last updated · ● Live · Refresh" strip for the dashboard header. Freshness
 * is the age of the most recent successful dashboard fetch -- prices poll every
 * 30s, so it only drifts to Delayed/Stale when fetching keeps failing. */
export function DataFreshnessStatus() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fetching = useIsFetching({ predicate: isDashboardQuery }) > 0
  const [lastUpdated, setLastUpdated] = useState(0)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const cache = queryClient.getQueryCache()
    const read = () => {
      const times = cache.findAll({ predicate: isDashboardQuery }).map((q) => q.state.dataUpdatedAt)
      setLastUpdated(times.length ? Math.max(...times) : 0)
    }
    read()
    return cache.subscribe(read)
  }, [queryClient])

  // Re-evaluate the age even when nothing refetches (e.g. backend unreachable).
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  const fresh = lastUpdated ? freshnessOf(Math.max(0, (now - lastUpdated) / 60_000)) : null

  return (
    <div className="flex items-center gap-2">
      <span className="rounded bg-[var(--badge-bg)] px-2 py-0.5 font-mono-num text-[10px] text-[var(--text-dimmed)]">
        {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : "—"}
      </span>
      <Badge variant={fresh?.variant ?? "unknown"}>● {t(fresh?.key ?? "freshness_no_data")}</Badge>
      <button
        type="button"
        onClick={() => {
          setNow(Date.now())
          void queryClient.invalidateQueries({ predicate: isDashboardQuery })
        }}
        disabled={fetching}
        className="flex items-center gap-1.5 rounded border border-[var(--border-primary)] bg-[var(--badge-bg)] px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] disabled:opacity-60"
      >
        <RefreshCw className={cn("h-3 w-3", fetching && "animate-spin")} />
        {t("freshness_refresh")}
      </button>
    </div>
  )
}
