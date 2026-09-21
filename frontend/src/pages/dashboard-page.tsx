import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { CompanyList } from "@/components/dashboard/company-list"
import { ReasonReportCard } from "@/components/dashboard/reason-report-card"
import { CreateReasonForm } from "@/components/dashboard/create-reason-form"
import { RecordPurchaseForm } from "@/components/dashboard/record-purchase-form"
import { useCompanies } from "@/hooks/use-companies"
import { useReport } from "@/hooks/use-report"
import { useDeleteReason, useReasons } from "@/hooks/use-reasons"
import { useTranslation } from "@/i18n/context"

export function DashboardPage() {
  const { t } = useTranslation()
  const { data: companies } = useCompanies()
  const [searchParams] = useSearchParams()
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null)

  // A link from elsewhere (e.g. the Portfolio page's "View details") can
  // deep-link straight to a company via ?ticker=; otherwise default to the
  // first company once the list loads.
  useEffect(() => {
    if (selectedTicker || !companies || companies.length === 0) return
    const fromUrl = searchParams.get("ticker")?.toUpperCase()
    const match = fromUrl && companies.find((c) => c.ticker === fromUrl)
    setSelectedTicker(match ? match.ticker : companies[0].ticker)
  }, [companies, selectedTicker, searchParams])

  const {
    data: report,
    isLoading: reportLoading,
    isError: reportError,
  } = useReport(selectedTicker ?? "")
  const { data: reasons } = useReasons(selectedTicker ?? "")
  const deleteReason = useDeleteReason()

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[240px_1fr]">
      <div className="lg:sticky lg:top-8 lg:h-[calc(100vh-4rem)]">
        <CompanyList selectedTicker={selectedTicker} onSelect={setSelectedTicker} />
      </div>

      <div className="flex flex-col gap-6">
        {!selectedTicker && (
          <p className="text-sm text-muted-foreground">{t("dashboard_select_company")}</p>
        )}

        {selectedTicker && (
          <>
            <div>
              <h1 className="text-xl font-extrabold">
                {report?.company_name ?? selectedTicker}{" "}
                <span className="font-mono-num text-sm font-medium text-muted-foreground">
                  {selectedTicker}
                </span>
              </h1>
              <p className="text-sm text-muted-foreground">
                {t("dashboard_report_subtitle")}
              </p>
            </div>

            {reportLoading && <p className="text-sm text-muted-foreground">{t("dashboard_report_loading")}</p>}
            {reportError && (
              <p className="text-sm text-destructive">
                {t("dashboard_report_error", { ticker: selectedTicker })}
              </p>
            )}

            {report && report.reasons.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t("dashboard_no_reasons", { ticker: selectedTicker })}
              </p>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {report?.reasons.map((rr) => {
                const meta = reasons?.find((r) => r.reason_key === rr.reason_key)
                return (
                  <ReasonReportCard
                    key={rr.reason_key}
                    reportReason={rr}
                    reasonMeta={meta}
                    deletable={meta ? !meta.is_builtin : false}
                    onDelete={() => deleteReason.mutate(rr.reason_key)}
                  />
                )
              })}
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <CreateReasonForm ticker={selectedTicker} />
              <RecordPurchaseForm ticker={selectedTicker} reasons={report?.reasons ?? []} />
            </div>
          </>
        )}
      </div>
    </div>
  )
}
