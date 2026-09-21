import { useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Bell, RefreshCw } from "lucide-react"
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
        <div className="absolute right-0 top-full z-30 mt-2 w-80 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-card)] shadow-xl">
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
                  className="rounded px-1.5 py-0.5 text-[11px] text-[var(--accent-blue)] hover:underline"
                >
                  {t("notifications_mark_all_read")}
                </button>
              )}
            </div>
          </div>

          <div className="max-h-80 overflow-y-auto">
            {notifications.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-[var(--text-ghost)]">
                {t("notifications_empty")}
              </p>
            ) : (
              notifications.map((n) => (
                <Link
                  key={n.id}
                  to={`/?ticker=${encodeURIComponent(n.ticker)}`}
                  onClick={() => {
                    if (!n.is_read) markRead.mutate(n.id)
                    setOpen(false)
                  }}
                  className={cn(
                    "block border-b border-[var(--border-secondary)] px-3 py-2.5 text-xs transition-colors last:border-0 hover:bg-[var(--bg-hover)]",
                    !n.is_read && "bg-[var(--accent-blue)]/5",
                  )}
                >
                  <div className="flex items-start gap-2">
                    {!n.is_read && (
                      <span className="mt-1 h-1.5 w-1.5 flex-none rounded-full bg-[var(--accent-blue)]" />
                    )}
                    <div className={cn("min-w-0", n.is_read && "pl-3.5")}>
                      <p className="text-[var(--text-primary)]">{n.message}</p>
                      <p className="mt-0.5 font-mono-num text-[10px] text-[var(--text-ghost)]">
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
