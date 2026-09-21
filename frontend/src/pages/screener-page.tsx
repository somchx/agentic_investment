import { useMemo, useState } from "react"
import { Info } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/status-badge"
import { useReasons } from "@/hooks/use-reasons"
import { useScreen } from "@/hooks/use-screen"
import { useTranslation } from "@/i18n/context"

export function ScreenerPage() {
  const { t, tReason } = useTranslation()
  const { data: reasons, isLoading: reasonsLoading } = useReasons()
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [activeKeys, setActiveKeys] = useState<string[]>([])

  const { data, isFetching, isError } = useScreen(activeKeys)

  const selectedReasons = useMemo(
    () => (reasons ?? []).filter((r) => activeKeys.includes(r.reason_key)),
    [reasons, activeKeys],
  )

  function toggleKey(key: string) {
    setSelectedKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-extrabold">{t("screener_title")}</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("screener_intro")}
        </p>
      </div>

      <Panel title={t("screener_choose_rules_title")} color="var(--accent-purple)" className="max-w-xl bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg p-4">
        <p className="mb-3 text-xs text-[var(--text-muted)]">{t("screener_choose_rules_description")}</p>

        <div className="flex flex-col gap-4">
          {reasonsLoading && <p className="text-sm text-muted-foreground">{t("screener_loading_reasons")}</p>}

          {!reasonsLoading && (reasons ?? []).length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("screener_no_reasons")}
            </p>
          )}

          <div className="flex flex-col gap-2">
            {(reasons ?? []).map((r) => (
              <label
                key={r.reason_key}
                className="flex cursor-pointer items-start gap-2.5 rounded-md border border-[var(--border-primary)] p-2.5 text-sm hover:bg-[var(--bg-hover)]"
              >
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 flex-none accent-primary"
                  checked={selectedKeys.includes(r.reason_key)}
                  onChange={() => toggleKey(r.reason_key)}
                />
                <span>
                  <span className="font-mono-num text-xs text-muted-foreground">{r.ticker ?? t("screener_ticker_any")}</span>{" "}
                  — {tReason(r.reason_key, r.description)}
                </span>
              </label>
            ))}
          </div>

          <Button
            type="button"
            disabled={selectedKeys.length === 0 || isFetching}
            onClick={() => setActiveKeys(selectedKeys)}
            className="self-start"
          >
            {isFetching
              ? t("screener_running")
              : selectedKeys.length > 1
                ? t("screener_run_multi", { count: selectedKeys.length })
                : t("screener_run")}
          </Button>
        </div>
      </Panel>

      {activeKeys.length > 0 && (
        <div className="flex flex-col gap-4">
          <div className="flex items-start gap-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-xs text-[var(--text-muted)]">
            <Info className="mt-0.5 h-3.5 w-3.5 flex-none" />
            <p>
              {t("screener_disclaimer")}
            </p>
          </div>

          {isError && <p className="text-sm text-destructive">{t("screener_error")}</p>}

          {data && (
            <Panel color="var(--accent-blue)" className="bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg overflow-hidden p-0">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-xs">
                  <thead>
                    <tr className="border-b border-[var(--border-primary)] bg-[var(--bg-hover)] text-left">
                      <th className="py-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        {t("screener_table_company")}
                      </th>
                      {selectedReasons.map((r) => (
                        <th
                          key={r.reason_key}
                          className="py-2 px-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-muted)]"
                        >
                          {tReason(r.reason_key, r.description)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.companies.map((c) => (
                      <tr key={c.ticker} className="border-b border-[var(--border-secondary)] last:border-0">
                        <td className="py-2 px-3">
                          <p className="font-mono-num text-xs text-muted-foreground">{c.ticker}</p>
                          <p className="font-semibold">{c.company_name}</p>
                        </td>
                        {activeKeys.map((key) => {
                          const r = c.by_reason[key]
                          return (
                            <td key={key} className="py-2 px-3">
                              {r?.status ? (
                                <div className="flex flex-col items-start gap-1">
                                  <StatusBadge status={r.status} />
                                  <span className="font-mono-num text-xs text-muted-foreground">
                                    {r.computed_value ?? "—"}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-xs text-muted-foreground">{r?.error ?? t("screener_table_na")}</span>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}
        </div>
      )}
    </div>
  )
}
