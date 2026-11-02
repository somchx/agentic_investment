import { useMarketConfig } from "@/hooks/use-market"
import { Suspense, useEffect, useState } from "react"
import { Link, NavLink, Outlet, useLocation } from "react-router-dom"
import {
  ChevronLeft,
  ChevronRight,
  Globe,
  BriefcaseBusiness, FileText, ShieldCheck,
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
import { LogoMark } from "@/components/logo"
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
  const { t, lang } = useTranslation()
  return [
    {
      label: t("nav_section_main"),
      items: [
        { to: "/", label: t("nav_dashboard"), icon: LayoutDashboard, end: true },
        { to: "/portfolio", label: t("portfolio_title"), icon: BriefcaseBusiness, end: false },
        { to: "/screener", label: t("nav_screener"), icon: ScanSearch, end: false },
      ],
    },
    {
      label: t("nav_section_tools"),
      items: [
        { to: "/agent", label: t("nav_agent"), icon: Sparkles, end: false },
        { to: "/reports", label: lang === "th" ? "รายงาน" : "Reports", icon: FileText, end: false },
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
  "flex items-center gap-2.5 rounded-xl transition-all duration-150"
const navRowActive = "bg-teal-500/25 text-white font-semibold shadow-sm border border-teal-300/15"
const navRowInactive = "text-slate-300 hover:bg-white/10 hover:text-white"

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
            <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-slate-400 font-semibold">
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
                    collapsed ? "justify-center px-0 w-10 h-10 mx-auto" : "px-3 py-3 text-sm",
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

  const { lang } = useTranslation()
  const titles: Record<string,string> = {
    '/': t('nav_dashboard'), '/portfolio': t('portfolio_title'), '/companies': lang==='th'?'บริษัท':'Companies',
    '/watchlist': lang==='th'?'รายการติดตาม':'Watchlist', '/screener': t('nav_screener'), '/agent': t('nav_agent'),
    '/reports': lang==='th'?'รายงาน':'Reports', '/user': t('user_profile'),
  }
  return (
    <div className="app-shell flex h-dvh overflow-hidden bg-[var(--bg-primary)]">
      {mobileOpen && <button aria-label={t('sidebar_close')} onClick={()=>setMobileOpen(false)} className="fixed inset-0 z-40 bg-slate-950/50 md:hidden"/>}
      <aside className={cn('app-sidebar fixed inset-y-0 left-0 z-50 flex w-64 shrink-0 flex-col transition-[width,transform] duration-200 md:relative md:translate-x-0', rc?'md:w-20':'md:w-60',mobileOpen?'translate-x-0':'-translate-x-full')}>
        <Link to="/" className={cn('flex h-20 shrink-0 items-center gap-3 border-b border-white/10',rc?'justify-center':'px-6')}>
          <LogoMark size={34}/>{!rc&&<span className="text-lg font-semibold tracking-tight text-white">ReasonCheck</span>}
        </Link>
        <button type="button" onClick={()=>setMobileOpen(false)} aria-label={t('sidebar_close')} className="absolute right-2 top-6 p-2 text-white md:hidden"><X className="h-4 w-4"/></button>
        <SidebarNav collapsed={rc} onNavigate={()=>setMobileOpen(false)}/>
        {!rc&&<div className="mx-4 mb-5 rounded-xl border border-white/10 bg-white/5 p-4 text-xs leading-relaxed text-slate-300"><ShieldCheck className="mb-2 h-5 w-5 text-teal-300"/>{lang==='th'?'ลงทุนด้วยเหตุผล ติดตามด้วยหลักฐาน':'Invest with a reason. Follow the evidence.'}<p className="mt-1 text-[10px] text-slate-400">Investment Thesis Monitoring</p></div>}
        <button onClick={()=>setCollapsed(c=>!c)} aria-label={collapsed?t('sidebar_expand'):t('sidebar_collapse')} className="hidden h-12 items-center justify-center gap-2 border-t border-white/10 text-xs text-slate-300 hover:bg-white/5 md:flex">{rc?<ChevronRight size={16}/>:<><ChevronLeft size={16}/>{lang==='th'?'ย่อเมนู':'Collapse sidebar'}</>}</button>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-20 shrink-0 items-center justify-between gap-3 border-b border-[var(--border-primary)] bg-[var(--bg-card)] px-4 sm:px-8">
          <div className="flex min-w-0 items-center gap-3"><button onClick={()=>setMobileOpen(true)} aria-label={t('sidebar_open')} className="p-2 md:hidden"><Menu size={20}/></button><div><p className="text-[10px] font-semibold uppercase tracking-[.18em] text-muted-foreground">Workspace</p><p className="truncate text-sm font-semibold">{titles[location.pathname] || titles['/companies']}</p></div></div>
          <div className="flex items-center gap-1"><LanguageToggle/><button onClick={toggle} aria-label={theme==='dark'?t('theme_toggle_light'):t('theme_toggle_dark')} className="rounded-lg p-2 text-muted-foreground hover:bg-muted">{theme==='dark'?<Sun size={17}/>:<Moon size={17}/>}</button><NotificationBell/><div className="mx-2 hidden h-7 w-px bg-border sm:block"/><AccountChip/></div>
        </header>
        <main id="main-content" className="min-w-0 flex-1 overflow-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-[1440px]"><MarketSourceNotice/><Suspense fallback={<div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground"/></div>}><Outlet/></Suspense></div>
        </main>
      </div>
    </div>
  )
}

function MarketSourceNotice() {
  const { data } = useMarketConfig()
  const { t } = useTranslation()
  if (data?.price_type !== "daily_close") return null
  return <details className="mb-5 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] px-4 py-2.5 text-xs text-muted-foreground"><summary className="cursor-pointer font-medium">{t("market_daily_close")} · Alpha Vantage · AAPL / MSFT / AMZN / GOOGL / NVDA</summary><p className="pt-2 leading-relaxed">{t("market_daily_notice")}</p></details>
}
