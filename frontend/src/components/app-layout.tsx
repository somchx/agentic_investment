import { Suspense, useEffect, useState } from "react"
import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import {
  ChevronLeft,
  ChevronRight,
  Globe,
  LayoutDashboard,
  Loader2,
  LogOut,
  Menu,
  Moon,
  ScanSearch,
  Sparkles,
  Sun,
  User2,
  X,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/use-auth"
import { useTheme } from "@/theme/context"
import { useTranslation } from "@/i18n/context"
import { NotificationBell } from "@/components/notification-bell"
import { LogoMark, Wordmark } from "@/components/logo"
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/radix-select"

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768)
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 767px)")
    const onChange = () => setIsMobile(mql.matches)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [])
  return isMobile
}

function useNavSections() {
  const { t } = useTranslation()
  return [
    {
      label: t("nav_section_main"),
      items: [
        { to: "/", label: t("nav_dashboard"), icon: LayoutDashboard, end: true },
        { to: "/screener", label: t("nav_screener"), icon: ScanSearch, end: false },
      ],
    },
    {
      label: t("nav_section_tools"),
      items: [
        { to: "/agent", label: t("nav_agent"), icon: Sparkles, end: false },
      ],
    },
    {
      label: t("nav_section_account"),
      items: [
        { to: "/user", label: t("user_profile"), icon: User2, end: true },
      ],
    },
  ]
}

const navRowBase =
  "flex items-center gap-2.5 rounded-full transition-all duration-150"
const navRowActive = "bg-[var(--bg-hover)] text-[var(--text-primary)] font-medium"
const navRowInactive = "text-[var(--text-faint)] hover:bg-[var(--bg-card)] hover:text-[var(--text-primary)]"

// Icon-rail sidebar: nav only, no logo/account chrome inside it -- those
// live in the always-visible topbar instead (matches the reference
// project's AppSidebar, whose desktop <aside> carries nothing but
// sections + links; the mobile drawer alone repeats a small logo header
// above the nav since the topbar sits behind the drawer overlay there).
function SidebarNav({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate?: () => void
}) {
  const sections = useNavSections()

  return (
    <nav className={cn("no-scrollbar flex-1 overflow-y-auto py-2", collapsed ? "px-2" : "px-3")}>
      {sections.map((section) => (
        <div key={section.label} className="py-1">
          {!collapsed && (
            <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-[var(--text-ghost)] font-semibold">
              {section.label}
            </div>
          )}
          <div className="space-y-0.5">
            {section.items.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                onClick={onNavigate}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  cn(
                    navRowBase,
                    collapsed ? "justify-center px-0 w-10 h-10 mx-auto" : "px-3 py-2 text-[12px]",
                    isActive ? navRowActive : navRowInactive,
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={cn("h-4 w-4 flex-shrink-0", !isActive && "opacity-60")} />
                    {!collapsed && <span className="truncate">{label}</span>}
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  )
}

// Match pplus-inv-v1's labels, Radix Select, and responsive trigger.
const languageLabels = { en: "English", th: "ไทย (Thai)" } as const

function LanguageToggle() {
  const { lang, setLang, t } = useTranslation()

  return (
    <Select value={lang} onValueChange={(value) => {
      if (value === "en" || value === "th") setLang(value)
    }}>
      <SelectTrigger
        title={t("topbar_language")}
        aria-label={t("topbar_language")}
        className="language-select h-9 w-auto gap-1.5 border-0 bg-transparent px-2 hover:bg-accent focus:ring-0"
      >
        <Globe className="w-4 h-4 text-muted-foreground shrink-0" />
        <div className="hidden sm:block text-xs font-medium uppercase">{languageLabels[lang]}</div>
      </SelectTrigger>
      <SelectContent align="end" className="language-select">
        {(["en", "th"] as const).map((language) => (
          <SelectItem key={language} value={language}>{languageLabels[language]}</SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

// Avatar and name open the personal profile, as in pplus-inv-v1.
function AccountChip() {
  const { user, logout } = useAuth()
  const { t } = useTranslation()
  const name = user?.full_name || user?.email || "?"
  const initials = (user?.full_name
    ? user.full_name.trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0]).join("")
    : (user?.email ?? "?").slice(0, 2)).toUpperCase()

  return (
    <div className="flex items-center gap-2.5 pl-1">
      <Link to="/user" title={t("user_profile")} aria-label={t("user_profile")} className="flex items-center gap-2.5 rounded-full p-1 -m-1 hover:bg-muted/40 transition-colors">
        <div className="w-8 h-8 shrink-0 rounded-full bg-primary/10 flex items-center justify-center text-xs font-semibold text-primary">
          {initials}
        </div>
        <div className="hidden md:block max-w-[180px]">
          <div className="truncate text-xs font-medium leading-tight">{name}</div>
          <div className="truncate text-[10px] text-muted-foreground">{user?.email}</div>
        </div>
      </Link>
      <button type="button" onClick={logout} title={t("nav_logout")} aria-label={t("nav_logout")} className="rounded-full p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive transition-colors">
        <LogOut className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

export function AppLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const { theme, toggle } = useTheme()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const isMobile = useIsMobile()
  // Icon-rail mode only applies on desktop -- the mobile drawer always shows
  // full labels regardless of the desktop collapsed state.
  const rc = collapsed && !isMobile

  // Close the mobile drawer automatically whenever the route changes.
  useEffect(() => setMobileOpen(false), [location.pathname])

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[var(--bg-primary)]">
      {/* Full-width topbar, above both the sidebar and the content -- logo
          and brand live here now (always visible), not inside the sidebar. */}
      <header className="z-40 h-14 flex-none border-b border-[var(--border-primary)] bg-[var(--bg-card)]">
        <div className="flex h-14 items-center justify-between gap-2 px-3">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-label={t("sidebar_open")}
              className="grid h-9 w-9 flex-none place-items-center rounded-lg text-[var(--text-faint)] hover:bg-[var(--bg-hover)] md:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>
            <LogoMark size={28} className="flex-none text-[var(--text-primary)]" />
            <div className="hidden min-w-0 sm:block">
              <div className="truncate text-sm font-semibold leading-tight">
                <Wordmark />
              </div>
              <div className="truncate text-[9px] text-[var(--text-ghost)]">{t("app_subtitle")}</div>
            </div>
          </div>

          <div className="flex flex-none items-center gap-1">
            <LanguageToggle />
            <button
              type="button"
              onClick={toggle}
              title={theme === "dark" ? t("theme_toggle_light") : t("theme_toggle_dark")}
              className="rounded-lg p-2 text-[var(--text-faint)] transition-colors hover:bg-[var(--bg-hover)]"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <NotificationBell />
            <div className="mx-1 hidden h-6 w-px bg-[var(--border-primary)] sm:block" />
            <AccountChip />
          </div>
        </div>
      </header>

      <div className="flex flex-1 gap-2 overflow-hidden p-2 md:p-3 min-h-0">
        {/* Backdrop behind the mobile drawer. */}
        {mobileOpen && (
          <div onClick={() => setMobileOpen(false)} className="fixed inset-0 z-40 bg-black/50 md:hidden" />
        )}

        {/* Single sidebar, mobile drawer and desktop rail share one element
            -- matches the reference's AppSidebar (fixed+translate on mobile,
            relative+width on desktop) instead of mounting two separate
            trees. */}
        <aside
          className={cn(
            "fixed md:relative inset-y-0 left-0 z-50 md:z-auto h-full md:h-auto w-64",
            collapsed ? "md:w-[4.5rem]" : "md:w-60",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
            "md:translate-x-0 bg-[var(--bg-sidebar)] border-r md:border border-[var(--border-sidebar)] md:rounded-2xl flex flex-col shrink-0 shadow-xl transition-[width,transform] duration-300 ease-out",
          )}
        >
          {/* Desktop collapse toggle -- fixed to the sidebar's top-right
              corner in both states so it never jumps around. */}
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? t("sidebar_expand") : t("sidebar_collapse")}
            className="hidden md:grid absolute -right-3 top-5 z-10 h-6 w-6 place-items-center rounded-full border border-[var(--border-primary)] bg-[var(--bg-card)] text-[var(--text-faint)] shadow-sm transition-colors hover:text-[var(--text-primary)]"
          >
            {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
          </button>
          {/* Mobile close button. */}
          <button
            type="button"
            onClick={() => setMobileOpen(false)}
            aria-label={t("sidebar_close")}
            className="md:hidden absolute right-3 top-4 z-10 grid h-8 w-8 place-items-center rounded-lg text-[var(--text-faint)] hover:bg-[var(--bg-hover)]"
          >
            <X className="h-4 w-4" />
          </button>

          {/* Logo header -- mobile drawer only, matching the reference: the
              always-visible topbar covers the desktop rail, but the topbar
              sits behind the drawer overlay on mobile. */}
          {isMobile && (
            <div className="flex h-16 flex-none items-center gap-2.5 border-b border-[var(--border-sidebar)] px-4">
              <LogoMark size={28} className="flex-none text-[var(--text-primary)]" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-semibold leading-tight">
                  <Wordmark />
                </div>
                <div className="truncate text-[9px] text-[var(--text-ghost)]">{t("app_subtitle")}</div>
              </div>
            </div>
          )}

          <SidebarNav collapsed={rc} onNavigate={() => setMobileOpen(false)} />
        </aside>

        <main className="min-w-0 flex-1 overflow-auto px-3 sm:px-5">
          <Suspense fallback={<div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-[var(--text-muted)]" /></div>}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  )
}
