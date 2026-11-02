import { RuleResult } from "@/components/screener/rule-result"
import { FinancialDataOrigin } from "@/components/screener/financial-data-info"
import { CompanySummary } from "@/components/screener/company-summary"
import { useMemo, useState } from "react"
import { Info, CheckSquare, MinusSquare, Square, Play } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { StatusBadge } from "@/components/status-badge"
import { ThresholdGauge } from "@/components/dashboard/threshold-gauge"
import { useReasons } from "@/hooks/use-reasons"
import { useScreen } from "@/hooks/use-screen"
import { useTranslation } from "@/i18n/context"

export function ScreenerPage() {
  const { t, tReason } = useTranslation()
  const { data: reasons, isLoading: reasonsLoading } = useReasons()
  const [selectedKeys, setSelectedKeys] = useState<string[]>(["revenue_growth", "operating_margin", "debt_growth"])
  const [activeKeys, setActiveKeys] = useState<string[]>([])
  const [showResults, setShowResults] = useState(false)

  const { data, isFetching, isError, refetch } = useScreen(activeKeys)

  const selectedReasons = useMemo(
    () => activeKeys.flatMap(key => (reasons ?? []).filter(r => r.reason_key === key)),
    [reasons, activeKeys],
  )

  const allSelected = !!reasons?.length && reasons.every(reason => selectedKeys.includes(reason.reason_key))
  const someSelected = !allSelected && !!reasons?.some(reason => selectedKeys.includes(reason.reason_key))

  function toggleKey(key: string) {
    setSelectedKeys((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold">{t("screener_title")}</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("screener_intro")}
          </p>
        </div>
      </div>

      <FinancialDataOrigin />

      <section className="min-w-0 overflow-hidden rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)]" aria-label={t("screener_choose_rules_title")}>
        <div className="flex min-h-16 flex-wrap items-center justify-between gap-3 border-b border-[var(--border-primary)] px-3 py-3 sm:px-4">
          <div>
            <h2 className="text-sm font-semibold tracking-tight">{t("screener_choose_rules_title")} <span className="font-normal text-muted-foreground">— {reasons?.length ?? 0}</span></h2>
            <p className="mt-1 text-xs text-muted-foreground">{t("screener_choose_rules_description")}</p>
          </div>
          {selectedKeys.length > 0 && <Button type="button" size="sm" disabled={isFetching} onClick={() => {
            if (selectedKeys.length === activeKeys.length && selectedKeys.every(key => activeKeys.includes(key))) void refetch()
            else setActiveKeys([...selectedKeys])
            setShowResults(true)
          }}>
            <Play className="h-3.5 w-3.5" />
            {t(isFetching ? "screener_running" : "screener_run")}
          </Button>}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-[var(--bg-hover)] text-left text-xs text-muted-foreground">
              <tr className="[&>th]:px-4 [&>th]:py-3 [&>th]:font-medium">
                <th className="w-10 text-center">
                  <button type="button" role="checkbox" aria-label={t("screener_select_all")} aria-checked={allSelected ? true : someSelected ? "mixed" : false} disabled={!reasons?.length} onClick={() => setSelectedKeys(allSelected ? [] : (reasons ?? []).map(reason => reason.reason_key))} className="rounded p-0.5 hover:bg-[var(--bg-hover)] disabled:opacity-40">
                    {allSelected ? <CheckSquare className="h-4 w-4 text-primary" /> : someSelected ? <MinusSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4 opacity-50" />}
                  </button>
                </th>
                <th>{t("screener_rule_column")}</th>
                <th className="whitespace-nowrap">{t("create_global_reason_companies_label")}</th>
                <th>{t("screener_formula_column")}</th>
                <th className="whitespace-nowrap">{t("create_reason_field_threshold").replace(" (%)", "")}</th>

              </tr>
            </thead>
            <tbody>
              {reasonsLoading && <tr><td colSpan={5} className="py-12 text-center text-muted-foreground">{t("screener_loading_reasons")}</td></tr>}
              {!reasonsLoading && !reasons?.length && <tr><td colSpan={5} className="py-12 text-center text-muted-foreground">{t("screener_no_reasons")}</td></tr>}
              {(reasons ?? []).map(r => <tr key={r.reason_key} onClick={() => toggleKey(r.reason_key)} className={`cursor-pointer border-t border-[var(--border-secondary)] transition-colors hover:bg-[var(--bg-hover)] [&>td]:px-4 [&>td]:py-3 ${selectedKeys.includes(r.reason_key) ? "bg-primary/5" : ""}`}>
                <td className="text-center">
                  <button type="button" role="checkbox" aria-label={tReason(r.reason_key, r.description)} aria-checked={selectedKeys.includes(r.reason_key)} onClick={event => { event.stopPropagation(); toggleKey(r.reason_key) }} className="rounded p-0.5 hover:bg-[var(--bg-hover)]">
                    {selectedKeys.includes(r.reason_key) ? <CheckSquare className="h-4 w-4 text-primary" /> : <Square className="h-4 w-4 text-muted-foreground/40" />}
                  </button>
                </td>
                <td className="min-w-[300px]">
                  <p className="font-medium">{tReason(r.reason_key, r.description)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{t(r.is_builtin ? "financial_builtin_rule" : "financial_custom_rule")}</p>
                </td>
                <td className="whitespace-nowrap"><span className="rounded-full bg-[var(--bg-hover)] px-2.5 py-0.5 text-xs font-medium">{r.ticker ?? t("screener_ticker_any")}</span></td>
                <td className="font-mono-num text-xs">{r.rule_definition?.preview ?? `${r.metric}${r.kind === "margin_level" ? ` / ${r.denominator_metric}` : " (YoY)"}`}</td>
                <td className="whitespace-nowrap font-mono-num">{r.threshold == null ? "—" : `${r.comparison} ${Number((r.threshold * 100).toFixed(6))}${r.rule_definition?.unit === "USD" ? " USD" : "%"}`}</td>
              </tr>)}
            </tbody>
          </table>
        </div>
      </section>

      <Dialog open={showResults} onOpenChange={setShowResults}>
        <DialogContent className="flex max-h-[85vh] w-[calc(100%-2rem)] max-w-6xl flex-col overflow-hidden p-4 sm:p-6">
          <DialogTitle className="shrink-0 pr-8">{t("screener_results_title")}</DialogTitle>
          <div className="min-h-0 overflow-y-auto space-y-4">
          <div className="flex items-start gap-2 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-3 text-xs text-[var(--text-muted)]">
            <Info className="mt-0.5 h-3.5 w-3.5 flex-none" />
            <p>
              {t("screener_disclaimer")}
            </p>
          </div>

          {isFetching && <p role="status" className="py-8 text-center text-sm text-muted-foreground">{t("screener_running")}</p>}
          {isError && !isFetching && <div role="alert" className="space-y-3 text-center">
            <p className="text-sm text-destructive">{t("screener_error")}</p>
            <Button variant="outline" onClick={() => void refetch()}>{t("screener_retry")}</Button>
          </div>}
          {data && !isFetching && !isError && data.companies.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">{t("screener_results_empty")}</p>}
          {data && !isFetching && !isError && data.companies.length > 0 && (
            <div className="space-y-3">
              {data.companies.map((c) => <CompanySummary key={c.ticker} company={c} reasonKeys={activeKeys} reasons={reasons} />)}
            </div>
          )}
          {data && !isFetching && !isError && data.companies.length > 0 && (
            <Panel color="var(--brand)" className="bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg overflow-hidden p-0">
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
                          const rule = reasons?.find((reason) => reason.reason_key === key)
                          return (
                            <td key={key} className="py-2 px-3 align-top">
                              {r?.status ? (
                                <div className="flex flex-col items-start gap-1.5">
                                  {r.rule_status ? <RuleResult result={r}/> : <StatusBadge status={r.status} />}
                                  {r.computed_value != null && rule && !rule.rule_definition && rule.threshold != null ? (
                                    <ThresholdGauge
                                      rows={[{ value: r.computed_value, status: r.status, title: r.as_of ? t("reason_card_as_of", { date: r.as_of }) : undefined }]}
                                      threshold={rule.threshold}
                                      comparison={rule.comparison}
                                    />
                                  ) : null}
                                  {r.as_of && <span className="text-[10px] text-[var(--text-muted)]">{t("reason_chart_latest", { date: r.as_of })}</span>}
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
        </DialogContent>
      </Dialog>
    </div>
  )
}
