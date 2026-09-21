import { useState } from "react"
import { NavLink, Outlet } from "react-router-dom"
import {
  ChevronLeft,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  ScanSearch,
  Sparkles,
  Sun,
  User2,
  Wallet,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/use-auth"
import { useTheme } from "@/theme/context"
import { useTranslation } from "@/i18n/context"
import { NotificationBell } from "@/components/notification-bell"
import { LogoMark, Wordmark } from "@/components/logo"

function useNavSections() {
  const { t } = useTranslation()
  return [
    {
      label: t("nav_section_main"),
      items: [
        { to: "/", label: t("nav_dashboard"), icon: LayoutDashboard, end: true },
        { to: "/screener", label: t("nav_screener"), icon: ScanSearch, end: false },
        { to: "/portfolio", label: t("nav_portfolio"), icon: Wallet, end: false },
      ],
    },
    {
      label: t("nav_section_tools"),
      items: [
        { to: "/agent", label: t("nav_agent"), icon: Sparkles, end: false },
        { to: "/profiles", label: t("nav_profiles"), icon: User2, end: false },
      ],
    },
  ]
}

function LanguageToggle() {
  const { lang, setLang, t } = useTranslation()
  return (
    <div className="flex items-center gap-0.5 rounded-md border border-[var(--border-primary)] bg-[var(--bg-hover)] p-0.5">
      <button
        type="button"
        onClick={() => setLang("en")}
        className={cn(
          "rounded px-2 py-1 text-[11px] font-semibold text-[var(--text-faint)] transition-colors",
          lang === "en" && "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]",
        )}
        aria-pressed={lang === "en"}
      >
        {t("lang_toggle_en")}
      </button>
      <button
        type="button"
        onClick={() => setLang("th")}
        className={cn(
          "rounded px-2 py-1 text-[11px] font-semibold text-[var(--text-faint)] transition-colors",
          lang === "th" && "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]",
        )}
        aria-pressed={lang === "th"}
      >
        {t("lang_toggle_th")}
      </button>
    </div>
  )
}

const navRowBase =
  "flex items-center gap-2.5 mx-2 px-2.5 py-2 rounded-full text-[13px] transition-colors"
const navRowActive = "bg-gradient-to-r from-[#f97316] to-[#ea580c] text-white font-medium shadow-glow"
const navRowInactive = "text-[var(--text-faint)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"

function SidebarContent({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate?: () => void
}) {
  const { user, logout } = useAuth()
  const { t } = useTranslation()
  const { theme, toggle } = useTheme()
  const sections = useNavSections()

  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          "flex h-16 flex-none items-center border-b border-[var(--border-sidebar)]",
          collapsed ? "justify-center px-0" : "gap-2.5 px-4",
        )}
      >
        <LogoMark size={34} className="shrink-0 text-[var(--text-primary)]" />
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold leading-tight">
              <Wordmark />
            </div>
            <div className="truncate text-[9px] text-[var(--text-ghost)]">{t("app_subtitle")}</div>
          </div>
        )}
      </div>

      <nav className="flex flex-1 flex-col gap-3 overflow-y-auto pb-3">
        {sections.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className="mx-4 mb-1 mt-2 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-ghost)]">
                {section.label}
              </div>
            )}
            <div className="flex flex-col gap-0.5">
              {section.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={onNavigate}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) =>
                    cn(navRowBase, collapsed && "justify-center px-0", isActive ? navRowActive : navRowInactive)
                  }
                >
                  <Icon className="h-[18px] w-[18px] flex-none" />
                  {!collapsed && <span className="truncate">{label}</span>}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="flex flex-none flex-col gap-2 border-t border-[var(--border-secondary)] px-2 py-3">
        {!collapsed && user?.email && (
          <div className="truncate px-2.5 font-mono-num text-[11px] text-[var(--text-muted)]" title={user.email}>
            {user.email}
          </div>
        )}
        <button
          type="button"
          onClick={toggle}
          title={theme === "dark" ? t("theme_toggle_light") : t("theme_toggle_dark")}
          className={cn(
            "flex items-center gap-2.5 rounded-full px-2.5 py-2 text-[13px] text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]",
            collapsed && "justify-center px-0",
          )}
        >
          {theme === "dark" ? <Sun className="h-[18px] w-[18px] flex-none" /> : <Moon className="h-[18px] w-[18px] flex-none" />}
          {!collapsed && <span>{theme === "dark" ? t("theme_toggle_light") : t("theme_toggle_dark")}</span>}
        </button>
        <button
          type="button"
          onClick={logout}
          title={t("nav_logout")}
          className={cn(
            "flex items-center gap-2.5 rounded-full px-2.5 py-2 text-[13px] text-[var(--text-faint)] transition-colors hover:bg-[var(--accent-red)]/10 hover:text-[var(--accent-red)]",
            collapsed && "justify-center px-0",
          )}
        >
          <LogOut className="h-[18px] w-[18px] flex-none" />
          {!collapsed && <span>{t("nav_logout")}</span>}
        </button>
      </div>
    </div>
  )
}

export function AppLayout() {
  const { t } = useTranslation()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-[var(--bg-primary)] md:gap-3 md:p-3">
      {/* Desktop sidebar: floating rounded panel, collapsible between a
          full nav rail and an icon-only rail. */}
      <aside
        className={cn(
          "relative hidden flex-none flex-col rounded-2xl border border-[var(--border-sidebar)] bg-[var(--bg-sidebar)] shadow-[0_8px_32px_-12px_rgba(0,0,0,0.45)] transition-[width] duration-200 md:flex",
          collapsed ? "md:w-[72px]" : "md:w-60",
        )}
      >
        <SidebarContent collapsed={collapsed} />
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? t("sidebar_expand") : t("sidebar_collapse")}
          className="absolute -right-3 top-5 flex h-6 w-6 items-center justify-center rounded-full border border-[var(--border-primary)] bg-[var(--bg-card)] text-[var(--text-faint)] shadow-sm transition-colors hover:text-[var(--text-primary)]"
        >
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
        </button>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setMobileOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-72 flex-col border-r border-[var(--border-sidebar)] bg-[var(--bg-sidebar)]">
            {/* Overlaps the h-16 logo row instead of taking its own row
                above it, matching the reference sidebar exactly. */}
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label={t("sidebar_close")}
              className="absolute right-3 top-4 z-10 grid h-8 w-8 place-items-center rounded-lg text-[var(--text-faint)] hover:bg-[var(--bg-hover)]"
            >
              <X className="h-4 w-4" />
            </button>
            <div className="min-h-0 flex-1">
              <SidebarContent collapsed={false} onNavigate={() => setMobileOpen(false)} />
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex h-14 flex-none items-center justify-between border-b border-[var(--border-primary)] bg-[var(--bg-sidebar)] px-4 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={t("sidebar_open")}
            className="rounded-md p-1.5 text-[var(--text-faint)] hover:bg-[var(--bg-hover)]"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex min-w-0 items-center gap-2">
            <LogoMark size={24} className="text-[var(--text-primary)]" />
            <span className="truncate text-sm font-semibold">
              <Wordmark />
            </span>
          </div>
          <div className="flex flex-none items-center gap-1.5">
            <LanguageToggle />
            <NotificationBell />
          </div>
        </header>

        {/* Desktop top bar -- same h-14/border-b/bg-sidebar treatment as the
            mobile top bar above, so the app has one consistent top-bar
            chrome on every breakpoint (the sidebar already carries brand +
            nav, so this one only needs the right-aligned controls). */}
        <header className="hidden h-14 flex-none items-center justify-end gap-3 border-b border-[var(--border-primary)] bg-[var(--bg-sidebar)] px-4 md:flex">
          <LanguageToggle />
          <NotificationBell />
        </header>

        <main className="min-w-0 flex-1 overflow-auto px-4 py-4 md:px-6 md:py-4">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
