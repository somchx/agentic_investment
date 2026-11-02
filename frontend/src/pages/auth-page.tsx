import { useState, type FormEvent } from "react"
import { ArrowRight, Lock, User } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { LogoMark, Wordmark } from "@/components/logo"
import { useAuth } from "@/hooks/use-auth"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"

function AuthForm({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth()
  const { t } = useTranslation()
  const [email, setEmail] = useState("")
  const [fullName, setFullName] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    // `required` lets a whitespace-only name through; the API would reject it with a generic error.
    if (mode === "register" && !fullName.trim()) { setError(t("user_name_required")); return }
    setSubmitting(true)
    try {
      if (mode === "login") {
        await login(email, password)
      } else {
        await register(email, password, fullName.trim())
      }
    } catch (err) {
      setError(getApiErrorMessage(err, t("auth_error_default")))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
      {mode === "register" && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="register-full-name">{t("user_full_name")}<span aria-hidden="true" className="ml-0.5 text-destructive">*</span></Label>
          <input
            id="register-full-name"
            autoComplete="name"
            required
            maxLength={200}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="h-11 w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 text-sm text-[var(--text-primary)] outline-none focus-visible:border-primary"
          />
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`${mode}-email`}>{t("auth_field_email")}{mode === "register" && <span aria-hidden="true" className="ml-0.5 text-destructive">*</span>}</Label>
        <div className="relative">
          <User className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--text-ghost)]" />
          <input
            id={`${mode}-email`}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-11 w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none transition-colors placeholder:text-[var(--text-ghost)] focus-visible:border-primary"
            placeholder="you@example.com"
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
            className="h-11 w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] pl-9 pr-3 text-sm text-[var(--text-primary)] outline-none transition-colors placeholder:text-[var(--text-ghost)] focus-visible:border-primary"
            placeholder="••••••••"
          />
        </div>
        {mode === "register" && (
          <p className="text-xs text-[var(--text-muted)]">{t("auth_password_hint")}</p>
        )}
      </div>
      {error && (
        <p className="rounded-md border border-[var(--accent-red)]/30 bg-[var(--accent-red)]/10 px-3 py-2 text-sm text-[var(--accent-red)]">
          {error}
        </p>
      )}
      <Button type="submit" disabled={submitting} size="lg" className="mt-1 w-full gap-2">
        {submitting ? t("auth_submit_pending") : mode === "login" ? t("auth_submit_login") : t("auth_submit_register")}
        {!submitting && <ArrowRight className="h-4 w-4" />}
      </Button>
    </form>
  )
}

export function AuthPage() {
  const [tab, setTab] = useState<"login" | "register">("login")
  const { t } = useTranslation()

  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--bg-primary)] px-4 py-10">
      <div className="w-full max-w-sm">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--border-primary)] bg-[var(--bg-card)]">
            <LogoMark size={28} />
          </div>
          <h1 className="mt-4 font-heading text-xl font-extrabold text-[var(--text-primary)]">
            <Wordmark />
          </h1>
          <p className="mt-1.5 text-sm text-[var(--text-muted)]">{t("auth_tagline")}</p>
        </div>

        <div className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] p-6 shadow-lg sm:p-7">
          <Tabs value={tab} onValueChange={(v) => setTab(v as "login" | "register")}>
            <TabsList className="w-full">
              <TabsTrigger value="login" className="flex-1">
                {t("auth_login_tab")}
              </TabsTrigger>
              <TabsTrigger value="register" className="flex-1">
                {t("auth_register_tab")}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="login" className="mt-5">
              <AuthForm mode="login" />
            </TabsContent>
            <TabsContent value="register" className="mt-5">
              <AuthForm mode="register" />
            </TabsContent>
          </Tabs>
        </div>

        <p className="mt-6 text-center text-xs text-[var(--text-ghost)]">{t("auth_footer_tagline")}</p>
      </div>
    </div>
  )
}
