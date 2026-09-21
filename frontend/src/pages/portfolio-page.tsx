import { Sparkles, Trash2 } from "lucide-react"
import { Link } from "react-router-dom"
import { Panel } from "@/components/ui/panel"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { usePortfolioSummary, useDeletePosition } from "@/hooks/use-positions"
import { useTranslation } from "@/i18n/context"

export function PortfolioPage() {
  const { t, tReason } = useTranslation()
  const { data, isLoading, isError } = usePortfolioSummary()
  const deletePosition = useDeletePosition()

  const statusLabel = (status: string) => t("status_" + status.toLowerCase().replace(/ /g, "_"))

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold">{t("portfolio_title")}</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            {t("portfolio_intro")}
          </p>
        </div>
        <Link
          to="/agent"
          className="inline-flex flex-none items-center gap-1.5 rounded-md border border-[var(--border-primary)] bg-[var(--bg-card)] px-3 py-1.5 text-xs font-medium text-[var(--text-faint)] transition-colors hover:border-[var(--accent-purple)]/50 hover:text-[var(--text-primary)]"
        >
          <Sparkles className="h-3.5 w-3.5 text-[var(--accent-purple)]" />
          {t("portfolio_ask_agent")}
        </Link>
      </div>

      {isLoading && <p className="text-sm text-muted-foreground">{t("portfolio_loading")}</p>}
      {isError && <p className="text-sm text-destructive">{t("portfolio_error")}</p>}
      {data && data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          {t("portfolio_empty")}
        </p>
      )}

      <div className="flex flex-col gap-6">
        {data?.map((company) => (
          <Panel
            key={company.ticker}
            color="var(--accent-blue)"
            title={
              <span className="inline-flex items-center gap-2 normal-case tracking-normal text-sm font-bold text-[var(--text-primary)]">
                {company.company_name}
                <span className="font-mono-num text-xs font-medium text-muted-foreground">
                  {company.ticker}
                </span>
              </span>
            }
          >
            <div className="flex flex-col gap-3">
              {company.positions.map((p) => (
                <div
                  key={p.id}
                  className="flex flex-col gap-3 rounded-md border border-border p-3 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="flex flex-col gap-1">
                    <div className="font-mono-num text-sm">
                      {t("portfolio_position_summary", {
                        quantity: p.quantity,
                        price: p.purchase_price,
                        date: p.purchase_date,
                      })}
                    </div>
                    {p.reason_snapshot ? (
                      <>
                        <div className="text-xs text-muted-foreground">
                          {t("portfolio_bought_for", {
                            description: tReason(p.reason_key, p.reason_snapshot.description),
                            status: statusLabel(p.reason_snapshot.status_at_purchase),
                          })}
                        </div>
                        {p.current_computed_value !== undefined && (
                          <div className="font-mono-num text-xs text-muted-foreground">
                            {t("portfolio_value_at_purchase")}{" "}
                            <span className="text-foreground">
                              {p.reason_snapshot.computed_value_at_purchase ?? "—"}
                            </span>
                            {"  →  "}
                            {t("portfolio_value_now")}{" "}
                            <span
                              className={
                                p.still_true === false ? "text-status-broken" : "text-status-supported"
                              }
                            >
                              {p.current_computed_value ?? "—"}
                            </span>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-xs text-muted-foreground">{t("portfolio_no_reason")}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    {p.still_true === null ? (
                      <Badge variant="unknown">{t("portfolio_status_unknown")}</Badge>
                    ) : p.still_true ? (
                      <Badge variant="supported">{t("portfolio_status_still_true")}</Badge>
                    ) : (
                      <Badge variant="broken">{t("portfolio_status_broken")}</Badge>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={t("portfolio_delete_position_aria")}
                      onClick={() => deletePosition.mutate(p.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}
