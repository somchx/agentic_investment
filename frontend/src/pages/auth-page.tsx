import { useState, type FormEvent } from "react"
import { ArrowRight, FileCheck, Lock, ScanSearch, TrendingUp, User } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/hooks/use-auth"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"

function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth()
  const { t } = useTranslation()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      if (mode === "login") {
        await login(email, password)
      } else {
        await register(email, password)
      }
    } catch (err) {
      setError(getApiErrorMessage(err, t("auth_error_default")))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${mode}-email`}>{t("auth_field_email")}</Label>
        <div className="relative">
          <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-ghost)]" />
          <input
            id={`${mode}-email`}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-10 w-full rounded-xl border border-[var(--border-primary)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none transition-colors focus-visible:border-[var(--accent-blue)] focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]"
          />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${mode}-password`}>{t("auth_field_password")}</Label>
        <div className="relative">
          <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-ghost)]" />
          <input
            id={`${mode}-password`}
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="h-10 w-full rounded-xl border border-[var(--border-primary)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none transition-colors focus-visible:border-[var(--accent-blue)] focus-visible:ring-1 focus-visible:ring-[var(--accent-blue)]"
          />
        </div>
        {mode === "register" && (
          <p className="text-xs text-[var(--text-muted)]">{t("auth_password_hint")}</p>
        )}
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button
        type="submit"
        disabled={submitting}
        className="mt-1 h-11 gap-2 rounded-xl bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)] font-semibold text-white hover:opacity-90"
      >
        {submitting ? t("auth_submit_pending") : mode === "login" ? t("auth_submit_login") : t("auth_submit_register")}
        {!submitting && <ArrowRight className="h-4 w-4" />}
      </Button>
    </form>
  )
}

function LogoMark({ size = 56 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path
        d="M14 2.5 4 6.3v6.3c0 6.3 4.2 11.9 10 13.9 5.8-2 10-7.6 10-13.9V6.3L14 2.5Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
        fill="currentColor"
        fillOpacity="0.06"
      />
      <path
        d="M9.5 14.2 12.6 17.3 18.7 10.5"
        stroke="var(--accent-blue)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Feature({
  icon: Icon,
  title,
  desc,
}: {
  icon: typeof FileCheck
  title: string
  desc: string
}) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)]/60 p-4 backdrop-blur">
      <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]">
        <Icon className="h-[18px] w-[18px]" />
      </div>
      <div>
        <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
        <p className="mt-0.5 text-xs text-[var(--text-muted)]">{desc}</p>
      </div>
    </div>
  )
}

export function AuthPage() {
  const [tab, setTab] = useState<"login" | "register">("login")
  const { t } = useTranslation()

  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center px-4 py-10"
      style={{
        background:
          "radial-gradient(1100px 620px at 50% 32%, rgba(37,99,235,0.18), transparent 62%), var(--bg-primary)",
      }}
    >
      <div className="flex w-full max-w-5xl flex-col items-center gap-8 xl:flex-row xl:items-stretch xl:justify-center">
        <div className="hidden w-full max-w-xs flex-col justify-center gap-3 xl:flex">
          <Feature
            icon={FileCheck}
            title={t("auth_feature_evidence_title")}
            desc={t("auth_feature_evidence_desc")}
          />
          <Feature
            icon={ScanSearch}
            title={t("auth_feature_screening_title")}
            desc={t("auth_feature_screening_desc")}
          />
        </div>

        <div className="w-full max-w-[460px] rounded-[28px] border border-[var(--border-primary)] bg-[var(--bg-card)]/60 p-8 shadow-2xl backdrop-blur-xl sm:p-10">
          <div className="flex flex-col items-center text-center">
            <LogoMark size={56} />
            <h1 className="mt-3 font-heading text-lg font-extrabold text-[var(--text-primary)]">
              {t("auth_app_title")}
            </h1>
            <p className="mt-1 text-sm text-[var(--text-muted)]">{t("auth_tagline")}</p>
            <div className="mt-4 h-[3px] w-16 rounded-full bg-gradient-to-r from-[var(--accent-blue)] to-[var(--accent-purple)]" />
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as "login" | "register")} className="mt-6">
            <TabsList className="w-full">
              <TabsTrigger value="login" className="flex-1">
                {t("auth_login_tab")}
              </TabsTrigger>
              <TabsTrigger value="register" className="flex-1">
                {t("auth_register_tab")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="login">
              <AuthForm mode="login" />
            </TabsContent>
            <TabsContent value="register">
              <AuthForm mode="register" />
            </TabsContent>
          </Tabs>
        </div>

        <div className="hidden w-full max-w-xs flex-col justify-center gap-3 xl:flex">
          <Feature
            icon={TrendingUp}
            title={t("auth_feature_thesis_title")}
            desc={t("auth_feature_thesis_desc")}
          />
        </div>
      </div>

      <p className="mt-8 max-w-md text-center text-[11px] text-[var(--text-ghost)]">{t("auth_footer_tagline")}</p>
    </div>
  )
}
