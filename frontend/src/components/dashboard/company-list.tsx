import { useState } from "react"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useCompanies } from "@/hooks/use-companies"
import type { Company } from "@/types"
import { useTranslation } from "@/i18n/context"

interface CompanyListProps {
  selectedTicker: string | null
  onSelect: (ticker: string) => void
}

export function CompanyList({ selectedTicker, onSelect }: CompanyListProps) {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useCompanies()
  const [query, setQuery] = useState("")

  const filtered: Company[] = (data ?? []).filter(
    (c) =>
      c.ticker.toLowerCase().includes(query.toLowerCase()) ||
      c.name.toLowerCase().includes(query.toLowerCase()),
  )

  return (
    <div className="flex h-full flex-col gap-3">
      <Input
        placeholder={t("company_search_placeholder")}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="flex flex-col gap-1 overflow-y-auto">
        {isLoading && <p className="px-2 py-4 text-sm text-muted-foreground">{t("company_list_loading")}</p>}
        {isError && <p className="px-2 py-4 text-sm text-destructive">{t("company_list_error")}</p>}
        {!isLoading && !isError && filtered.length === 0 && (
          <p className="px-2 py-4 text-sm text-muted-foreground">{t("company_list_empty")}</p>
        )}
        {filtered.map((company) => (
          <button
            key={company.ticker}
            onClick={() => onSelect(company.ticker)}
            className={cn(
              "flex flex-col items-start rounded-md px-3 py-2 text-left transition-colors hover:bg-secondary",
              selectedTicker === company.ticker && "bg-primary/15",
            )}
          >
            <span
              className={cn(
                "font-mono-num text-xs font-bold tracking-wide",
                selectedTicker === company.ticker ? "text-primary" : "text-muted-foreground",
              )}
            >
              {company.ticker}
            </span>
            <span className="text-sm font-medium">{company.name}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
