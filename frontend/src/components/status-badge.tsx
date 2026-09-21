import { Badge } from "@/components/ui/badge"
import type { ReasonStatus } from "@/types"
import { useTranslation } from "@/i18n/context"

const STATUS_VARIANT: Record<ReasonStatus, "supported" | "weakened" | "broken" | "unknown"> = {
  Supported: "supported",
  Weakened: "weakened",
  Broken: "broken",
  "Not enough data": "unknown",
}

const STATUS_KEY: Record<ReasonStatus, string> = {
  Supported: "status_supported",
  Weakened: "status_weakened",
  Broken: "status_broken",
  "Not enough data": "status_not_enough_data",
}

export function StatusBadge({ status }: { status: ReasonStatus | string }) {
  const { t } = useTranslation()
  const variant = STATUS_VARIANT[status as ReasonStatus] ?? "unknown"
  const key = STATUS_KEY[status as ReasonStatus]
  return <Badge variant={variant}>{key ? t(key) : status}</Badge>
}
