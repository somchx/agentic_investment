import { useEffect, useRef, useState, type FormEvent } from "react"
import { Check, CheckCheck, ChevronDown, ChevronRight, Eye, EyeOff, KeyRound, Loader2, Mail, Save, ShieldCheck, User2, X } from "lucide-react"
import { useAuth } from "@/hooks/use-auth"
import { useTranslation } from "@/i18n/context"
import { getApiErrorMessage } from "@/api/client"

const inputClass = "h-11 w-full rounded-xl border border-input bg-[var(--bg-input)] px-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-ring focus:ring-2 focus:ring-ring/10 disabled:opacity-50"
const saveClass = "inline-flex h-10 items-center justify-center gap-2 rounded-xl brand-gradient px-5 text-sm font-medium text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card disabled:cursor-not-allowed disabled:opacity-40"
const secondaryClass = "inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-40"

function Feedback({ error, success }: { error: string; success: string }) {
  return <>
    {error && <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</p>}
    {success && <p role="status" className="flex items-start gap-2 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm text-foreground"><CheckCheck className="mt-0.5 h-4 w-4 shrink-0" />{success}</p>}
  </>
}

const passwordRules = [
  { key: "user_rule_length", test: (value: string) => value.length >= 8 },
  { key: "user_rule_upper", test: (value: string) => /[A-Z]/.test(value) },
  { key: "user_rule_lower", test: (value: string) => /[a-z]/.test(value) },
  { key: "user_rule_number", test: (value: string) => /[0-9]/.test(value) },
  { key: "user_rule_special", test: (value: string) => /[^a-zA-Z0-9]/.test(value) },
]

function PasswordField({ id, label, value, onChange, disabled, isNew = false, autoFocus = false }: {
  id: string; label: string; value: string; onChange: (value: string) => void; disabled: boolean; isNew?: boolean; autoFocus?: boolean
}) {
  const [show, setShow] = useState(false)
  const { t } = useTranslation()
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-xs font-medium text-foreground">{label}</label>
      <div className="relative">
        <input id={id} type={show ? "text" : "password"} autoComplete={isNew ? "new-password" : "current-password"} autoFocus={autoFocus} required maxLength={isNew ? 128 : undefined} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} className={`${inputClass} pr-11`} placeholder="••••••••" />
        <button type="button" disabled={disabled} aria-label={`${t(show ? "user_hide_password" : "user_show_password")}: ${label}`} aria-pressed={show} onClick={() => setShow(!show)} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-xl text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
      </div>
    </div>
  )
}

export function UserProfilePage() {
  const { user, updateProfile, changePassword } = useAuth()
  const { t } = useTranslation()
  const [fullName, setFullName] = useState(user?.full_name ?? "")
  const [email, setEmail] = useState(user?.email ?? "")
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileError, setProfileError] = useState("")
  const [profileSaved, setProfileSaved] = useState(false)
  const [passwordOpen, setPasswordOpen] = useState(false)
  const [current, setCurrent] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [passwordSaving, setPasswordSaving] = useState(false)
  const [passwordError, setPasswordError] = useState("")
  const [passwordSaved, setPasswordSaved] = useState(false)
  const passwordTrigger = useRef<HTMLButtonElement>(null)
  const busy = profileSaving || passwordSaving

  useEffect(() => {
    setFullName(user?.full_name ?? "")
    setEmail(user?.email ?? "")
  }, [user?.full_name, user?.email])

  const profileDirty = fullName.trim() !== (user?.full_name ?? "") || email.trim() !== (user?.email ?? "")
  const passwordDirty = Boolean(current || newPassword || confirm)
  const valid = passwordRules.every((rule) => rule.test(newPassword))
  const match = confirm.length > 0 && confirm === newPassword
  const score = Number(newPassword.length >= 8) + Number(newPassword.length >= 12) + Number(/[a-z]/.test(newPassword) && /[A-Z]/.test(newPassword)) + Number(/[0-9]/.test(newPassword)) + Number(/[^a-zA-Z0-9]/.test(newPassword))
  const strength = score <= 1 ? "weak" : score <= 2 ? "fair" : score <= 3 ? "good" : "strong"
  const strengthColor = score <= 1 ? "bg-destructive" : score <= 2 ? "bg-status-weakened" : score <= 3 ? "bg-primary" : "bg-status-supported"

  function resetProfile() {
    setFullName(user?.full_name ?? ""); setEmail(user?.email ?? "")
    setProfileError(""); setProfileSaved(false)
  }

  async function handleProfileSave(event: FormEvent) {
    event.preventDefault()
    setProfileError(""); setProfileSaved(false)
    if (!fullName.trim()) { setProfileError(t("user_name_required")); return }
    setProfileSaving(true)
    try {
      await updateProfile(fullName.trim(), email.trim())
      setProfileSaved(true)
    } catch (err) {
      setProfileError(getApiErrorMessage(err, t("user_save_failed")))
    } finally { setProfileSaving(false) }
  }

  function closePassword() {
    setCurrent(""); setNewPassword(""); setConfirm("")
    setPasswordError(""); setPasswordSaved(false); setPasswordOpen(false)
    passwordTrigger.current?.focus()
  }

  async function handlePasswordSave(event: FormEvent) {
    event.preventDefault()
    setPasswordError(""); setPasswordSaved(false)
    if (!current) { setPasswordError(t("user_current_password_required")); return }
    if (!valid) { setPasswordError(t("user_password_rules")); return }
    if (!match) { setPasswordError(t("user_password_mismatch")); return }
    if (current === newPassword) { setPasswordError(t("user_password_same")); return }
    setPasswordSaving(true)
    try {
      await changePassword(current, newPassword)
      setCurrent(""); setNewPassword(""); setConfirm("")
      setPasswordSaved(true)
    } catch (err) {
      setPasswordError(getApiErrorMessage(err, t("user_password_failed")))
    } finally { setPasswordSaving(false) }
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-7 py-5 sm:py-8">
      <header className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{t("user_settings_label")}</p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{t("user_profile")}</h1>
        <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">{t("user_settings_description")}</p>
      </header>

      <div>
        <div className="min-w-0 space-y-5">
          <form onSubmit={handleProfileSave} onChange={() => { setProfileError(""); setProfileSaved(false) }} aria-labelledby="personal-heading" className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="flex items-start gap-3 border-b border-border px-5 py-5 sm:px-6">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground"><User2 className="h-4 w-4" /></span>
              <div className="space-y-1"><h2 id="personal-heading" className="text-sm font-semibold">{t("user_section_personal")}</h2><p className="text-xs leading-relaxed text-muted-foreground">{t("user_personal_description")}</p></div>
            </div>
            <div className="space-y-5 p-5 sm:p-6">
              <div className="grid gap-5 xl:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="profile-full-name" className="text-xs font-medium">{t("user_full_name")}<span aria-hidden="true" className="ml-1 text-muted-foreground">*</span></label>
                  <input id="profile-full-name" autoComplete="name" required maxLength={200} value={fullName} onChange={(e) => setFullName(e.target.value)} disabled={busy} className={inputClass} />
                </div>
                <div className="space-y-2">
                  <label htmlFor="profile-email" className="text-xs font-medium">{t("auth_field_email")}<span aria-hidden="true" className="ml-1 text-muted-foreground">*</span></label>
                  <div className="relative"><Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><input id="profile-email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} disabled={busy} aria-describedby="email-help" className={`${inputClass} pl-9`} /></div>
                  <p id="email-help" className="text-[11px] leading-relaxed text-muted-foreground">{t("user_email_help")}</p>
                </div>
              </div>
              <Feedback error={profileError} success={profileSaved ? t("user_saved") : ""} />
            </div>
            <div className="flex flex-wrap items-center justify-end gap-3 border-t border-border bg-muted/20 px-5 py-4 sm:px-6">
              {profileDirty && <span className="mr-auto flex items-center gap-1.5 text-[11px] text-muted-foreground"><span className="h-1.5 w-1.5 rounded-full bg-current" />{t("user_unsaved")}</span>}
              {profileDirty && <button type="button" onClick={resetProfile} disabled={busy} className={secondaryClass}>{t("user_cancel")}</button>}
              <button type="submit" disabled={busy || !profileDirty} className={saveClass}>{profileSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{t(profileSaving ? "user_saving" : "user_save")}</button>
            </div>
          </form>

          <section aria-labelledby="security-heading" className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="flex items-start gap-3 border-b border-border px-5 py-5 sm:px-6">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground"><ShieldCheck className="h-4 w-4" /></span>
              <div className="space-y-1"><h2 id="security-heading" className="text-sm font-semibold">{t("user_section_security")}</h2><p className="text-xs leading-relaxed text-muted-foreground">{t("user_password_subtitle")}</p></div>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-6">
              <div className="flex items-center gap-3"><KeyRound className="h-4 w-4 text-muted-foreground" /><div><p className="text-xs font-medium">{t("auth_field_password")}</p><p aria-hidden="true" className="mt-1 text-sm tracking-[0.22em] text-muted-foreground">••••••••••</p></div></div>
              <button ref={passwordTrigger} type="button" onClick={() => passwordOpen ? closePassword() : setPasswordOpen(true)} disabled={busy} aria-expanded={passwordOpen} aria-controls="password-editor" className={secondaryClass}>{t("user_change_password")}{passwordOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}</button>
            </div>
            {passwordOpen && <form id="password-editor" onSubmit={handlePasswordSave} onChange={() => { setPasswordError(""); setPasswordSaved(false) }} className="border-t border-border">
              <div className="space-y-5 p-5 sm:p-6">
                <div className="max-w-sm"><PasswordField id="current-password" label={t("user_current_password")} value={current} onChange={setCurrent} disabled={busy} autoFocus /></div>
                <div className="grid gap-5 xl:grid-cols-2">
                  <PasswordField id="new-password" label={t("user_new_password")} value={newPassword} onChange={setNewPassword} disabled={busy} isNew />
                  <div className="space-y-2"><PasswordField id="confirm-password" label={t("user_confirm_password")} value={confirm} onChange={setConfirm} disabled={busy} isNew />{confirm && <p className={`flex items-center gap-1 text-[11px] ${match ? "text-status-supported" : "text-destructive"}`}>{match ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}{t(match ? "user_password_match" : "user_password_mismatch")}</p>}</div>
                </div>
                {newPassword && <div className="space-y-3 rounded-xl border border-border bg-background p-4">
                  <div className="flex items-center gap-3"><div className="flex h-1 flex-1 gap-1">{Array.from({ length: 5 }, (_, i) => <div key={i} className={`flex-1 rounded-full transition-colors ${i < score ? strengthColor : "bg-muted"}`} />)}</div><span className="text-[11px] font-medium">{t(`user_strength_${strength}`)}</span></div>
                  <ul className="grid gap-x-4 gap-y-2 sm:grid-cols-2">{passwordRules.map((rule) => {
                    const ok = rule.test(newPassword)
                    return <li key={rule.key} className={`flex items-center gap-1.5 text-[11px] ${ok ? "text-status-supported" : "text-muted-foreground"}`}>{ok ? <Check className="h-3 w-3" /> : <span className="mx-[3px] h-1.5 w-1.5 rounded-full bg-current opacity-40" />}{t(rule.key)}</li>
                  })}</ul>
                </div>}
                <Feedback error={passwordError} success={passwordSaved ? t("user_password_changed") : ""} />
              </div>
              <div className="flex flex-wrap justify-end gap-3 border-t border-border bg-muted/20 px-5 py-4 sm:px-6"><button type="button" onClick={closePassword} disabled={busy} className={secondaryClass}>{t("user_cancel")}</button><button type="submit" disabled={busy || !passwordDirty} className={saveClass}>{passwordSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}{t(passwordSaving ? "user_saving" : "user_change_password")}</button></div>
            </form>}
          </section>
        </div>
      </div>
    </div>
  )
}
