import type { PortfolioCompanySummary } from "@/types"

/** Use the same price snapshot and gains as the individual position rows. */
export function purchaseTotals(summary: PortfolioCompanySummary[] | undefined) {
  let cost = 0
  let value = 0
  let gain = 0
  let complete = !!summary?.length
  for (const company of summary ?? []) {
    if ("error" in company) { complete = false; continue }
    for (const position of company.positions) {
      cost += position.quantity * position.purchase_price
      if (position.current_price === null || position.unrealized_pnl === null) {
        complete = false
        continue
      }
      value += position.quantity * position.current_price
      gain += position.unrealized_pnl
    }
  }
  return {
    purchaseValue: complete ? value : null,
    purchaseGain: complete ? gain : null,
    purchaseGainPct: complete && cost > 0 ? gain / cost * 100 : null,
  }
}
