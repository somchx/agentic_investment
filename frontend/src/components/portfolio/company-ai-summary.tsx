import { InvestigationPanel } from "@/components/dashboard/investigation-panel"
import { useReport } from "@/hooks/use-report"
import { useDeleteReason, useReasons } from "@/hooks/use-reasons"

/** The dashboard modal's AI Summary panel (reason charts + stored AI
 * summary) for one held company on the Portfolio page. */
export function CompanyAiSummary({ ticker }: { ticker: string }) {
  const { data: report } = useReport(ticker)
  const { data: reasons } = useReasons(ticker)
  const deleteReason = useDeleteReason()

  return (
    <InvestigationPanel
      ticker={ticker}
      reasons={report?.reasons ?? []}
      dataFreshness={report?.data_freshness}
      reasonsMeta={reasons}
      onDeleteReason={(key) => deleteReason.mutate(key)}
      reasonsAnchorId={`reason-checks-${ticker}`}
    />
  )
}
