import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { ArrowRight, Bell, RefreshCw } from "lucide-react"
import { StatusBadge } from "@/components/status-badge"
import { ThresholdGauge } from "@/components/dashboard/threshold-gauge"
import type { AppNotification } from "@/types"
import { cn } from "@/lib/utils"
import { useTranslation } from "@/i18n/context"
import {
  useCheckNotificationsNow,
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotifications,
  useUnreadCount,
} from "@/hooks/use-notifications"

export function NotificationBell() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const { data: unreadCount = 0 } = useUnreadCount()
  const { data: notifications = [] } = useNotifications()
  const markRead = useMarkNotificationRead()
  const markAllRead = useMarkAllNotificationsRead()
  const checkNow = useCheckNotificationsNow()

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener("mousedown", onClickOutside)
    return () => document.removeEventListener("mousedown", onClickOutside)
  }, [])

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("notifications_title")}
        className="relative rounded-md p-2 text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-2 w-2 rounded-full bg-[var(--accent-red)]" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-30 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] shadow-xl">
          <div className="flex items-center justify-between gap-2 border-b border-[var(--border-primary)] px-3 py-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
              {t("notifications_title")}
            </span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => checkNow.mutate()}
                disabled={checkNow.isPending}
                aria-label={t("notifications_check_now")}
                title={t("notifications_check_now")}
                className="rounded p-1 text-[var(--text-ghost)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] disabled:opacity-50"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", checkNow.isPending && "animate-spin")} />
              </button>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={() => markAllRead.mutate()}
                  className="rounded px-1.5 py-0.5 text-[11px] text-primary hover:underline"
                >
                  {t("notifications_mark_all_read")}
                </button>
              )}
            </div>
          </div>

          <div className="max-h-[28rem] overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-[var(--text-ghost)]">
                {t("notifications_empty")}
              </p>
            ) : (
              notifications.map((n) => (
                <Link
                  key={n.id}
                  to={`/?holding=${encodeURIComponent(n.ticker)}`}
                  onClick={() => {
                    if (!n.is_read) markRead.mutate(n.id)
                    setOpen(false)
                  }}
                  className={cn(
                    "block border-b border-[var(--border-secondary)] px-3 py-2.5 text-xs transition-colors last:border-0 hover:bg-[var(--bg-hover)]",
                    !n.is_read && "bg-primary/5",
                  )}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="mt-1 h-1.5 w-1.5 flex-none rounded-full bg-primary" />
                    )}
                    <div className={cn("min-w-0 flex-1", n.is_read && "pl-3.5")}>
                      <NotificationBody n={n} />
                      <p className="mt-1 font-mono-num text-[10px] text-[var(--text-ghost)]">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Old notifications only carry the English `message`; newer ones render the
// change in the viewer's language: what changed, the before/after value on
// the threshold gauge, and which filing it came from.
function NotificationBody({ n }: { n: AppNotification }) {
  const { t, tReason } = useTranslation()
  if (!n.kind || !n.current_status) {
    return <p className="text-[var(--text-primary)]">{n.message}</p>
  }
  const headline =
    n.current_status === "Supported" ? "notification_met_again"
    : n.previous_status === "Supported" ? "notification_no_longer_met"
    : "notification_status_changed"
  const rows = [
    ...(n.previous_value != null && n.previous_status
      ? [{ label: n.previous_as_of ?? "", value: n.previous_value, status: n.previous_status }]
      : []),
    ...(n.computed_value != null ? [{ label: n.as_of ?? "", value: n.computed_value, status: n.current_status }] : []),
  ]
  return (
    <div className="flex flex-col gap-1.5">
      <p className="font-semibold text-[var(--text-primary)]">
        {n.ticker} · {t(headline)}
      </p>
      <p className="text-[var(--text-muted)]">{tReason(n.reason_key ?? "", n.reason_description ?? "")}</p>
      <div className="flex flex-wrap items-center gap-1">
        {n.previous_status && <StatusBadge status={n.previous_status} />}
        <ArrowRight className="h-3 w-3 text-[var(--text-ghost)]" />
        <StatusBadge status={n.current_status} />
      </div>
      {rows.length > 0 && n.threshold != null && n.comparison && (
        <ThresholdGauge rows={rows} threshold={n.threshold} comparison={n.comparison} />
      )}
      <span className="text-[11px] font-semibold text-primary">{t("notification_view_details")} →</span>
    </div>
  )
}
