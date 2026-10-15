import { useEffect, useState, type FormEvent } from "react"
import { Trash2 } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { useCreateProfile, useDeleteProfile, useProfiles } from "@/hooks/use-profiles"
import { useInvestorProfileSettings, useUpdateInvestorProfileSettings } from "@/hooks/use-investor-profile"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"

// "My Investor Profile" -- a singleton settings form (budget, target
// growth, horizon, risk tolerance, goals, notes) referenced server-side by
// the portfolio-wide AI chat agent, distinct from the reusable named
// presets below (which only feed the dashboard's paid /personalize
// feature and have no effect on chat).
function InvestorProfileSection() {
  const { t } = useTranslation()
  const { data: settings, isLoading } = useInvestorProfileSettings()
  const updateSettings = useUpdateInvestorProfileSettings()

  const [budget, setBudget] = useState("")
  const [targetGrowth, setTargetGrowth] = useState("")
  const [horizon, setHorizon] = useState("")
  const [risk, setRisk] = useState("")
  const [goals, setGoals] = useState("")
  const [notes, setNotes] = useState("")
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!settings) return
    setBudget(settings.budget_usd !== null ? String(settings.budget_usd) : "")
    setTargetGrowth(settings.target_growth_pct !== null ? String(settings.target_growth_pct) : "")
    setHorizon(settings.investment_horizon ?? "")
    setRisk(settings.risk_tolerance ?? "")
    setGoals(settings.goals ?? "")
    setNotes(settings.notes ?? "")
  }, [settings])

  const horizonOptions = [
    { value: "<1y", label: t("investor_profile_horizon_lt1y") },
    { value: "1-5y", label: t("investor_profile_horizon_1to5y") },
    { value: ">5y", label: t("investor_profile_horizon_gt5y") },
  ]
  const riskOptions = [
    { value: "low", label: t("investor_profile_risk_low") },
    { value: "medium", label: t("investor_profile_risk_medium") },
    { value: "high", label: t("investor_profile_risk_high") },
  ]

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSaved(false)
    try {
      await updateSettings.mutateAsync({
        budget_usd: budget.trim() ? Number(budget) : null,
        target_growth_pct: targetGrowth.trim() ? Number(targetGrowth) : null,
        investment_horizon: horizon || null,
        risk_tolerance: risk || null,
        goals: goals.trim() || null,
        notes: notes.trim() || null,
      })
      setSaved(true)
    } catch (err) {
      setError(getApiErrorMessage(err, t("investor_profile_error")))
    }
  }

  return (
    <Panel
      title={t("investor_profile_section_title")}
      description={t("investor_profile_section_intro")}
      color="var(--brand)"
      className="max-w-xl bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg p-4"
    >
      {isLoading ? (
        <p className="text-sm text-muted-foreground">{t("investor_profile_loading")}</p>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ip-budget">{t("investor_profile_field_budget")}</Label>
              <Input
                id="ip-budget"
                type="number"
                step="any"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ip-growth">{t("investor_profile_field_target_growth")}</Label>
              <Input
                id="ip-growth"
                type="number"
                step="any"
                value={targetGrowth}
                onChange={(e) => setTargetGrowth(e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ip-horizon">{t("investor_profile_field_horizon")}</Label>
              <Select
                id="ip-horizon"
                value={horizon}
                onChange={setHorizon}
                options={horizonOptions}
                placeholder={t("investor_profile_select_placeholder")}
                className="flex h-9 w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 text-sm text-[var(--text-primary)]"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="ip-risk">{t("investor_profile_field_risk")}</Label>
              <Select
                id="ip-risk"
                value={risk}
                onChange={setRisk}
                options={riskOptions}
                placeholder={t("investor_profile_select_placeholder")}
                className="flex h-9 w-full items-center justify-between gap-2 rounded border border-[var(--border-primary)] bg-[var(--bg-input)] px-3 text-sm text-[var(--text-primary)]"
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ip-goals">{t("investor_profile_field_goals")}</Label>
            <Textarea
              id="ip-goals"
              placeholder={t("investor_profile_goals_placeholder")}
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ip-notes">{t("investor_profile_field_notes")}</Label>
            <Textarea
              id="ip-notes"
              placeholder={t("investor_profile_notes_placeholder")}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={updateSettings.isPending} className="self-start">
              {updateSettings.isPending ? t("investor_profile_save_pending") : t("investor_profile_save")}
            </Button>
            {saved && !updateSettings.isPending && (
              <span className="text-sm text-status-supported">{t("investor_profile_saved")}</span>
            )}
          </div>
        </form>
      )}
    </Panel>
  )
}

export function ProfilesPage() {
  const { t } = useTranslation()
  const { data: profiles, isLoading, isError } = useProfiles()
  const createProfile = useCreateProfile()
  const deleteProfile = useDeleteProfile()

  const [name, setName] = useState("")
  const [riskTolerance, setRiskTolerance] = useState("")
  const [investmentHorizon, setInvestmentHorizon] = useState("")
  const [positionSizePct, setPositionSizePct] = useState("")
  const [objective, setObjective] = useState("")
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (!name.trim()) {
      setError(t("profiles_err_name"))
      return
    }
    const pct = Number(positionSizePct)
    if (Number.isNaN(pct)) {
      setError(t("profiles_err_size"))
      return
    }
    try {
      await createProfile.mutateAsync({
        name: name.trim(),
        risk_tolerance: riskTolerance,
        investment_horizon: investmentHorizon,
        position_size_pct: pct,
        objective,
      })
      setName("")
      setRiskTolerance("")
      setInvestmentHorizon("")
      setPositionSizePct("")
      setObjective("")
    } catch (err) {
      setError(getApiErrorMessage(err, t("profiles_err_default")))
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-extrabold">{t("profiles_title")}</h1>
      </div>

      <InvestorProfileSection />

      <div className="mt-2">
        <h2 className="text-base font-bold text-[var(--text-primary)]">{t("profiles_presets_title")}</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("profiles_intro")}
        </p>
      </div>

      <Panel
        title={t("profiles_new_title")}
        description={t("profiles_new_description")}
        color="var(--brand-secondary)"
        className="max-w-xl bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-lg p-4"
      >
          <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profile-name">{t("profiles_field_name")}</Label>
              <Input id="profile-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="profile-risk">{t("profiles_field_risk")}</Label>
                <Input
                  id="profile-risk"
                  placeholder={t("profiles_risk_placeholder")}
                  value={riskTolerance}
                  onChange={(e) => setRiskTolerance(e.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="profile-horizon">{t("profiles_field_horizon")}</Label>
                <Input
                  id="profile-horizon"
                  placeholder={t("profiles_horizon_placeholder")}
                  value={investmentHorizon}
                  onChange={(e) => setInvestmentHorizon(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profile-size">{t("profiles_field_size")}</Label>
              <Input
                id="profile-size"
                type="number"
                step="any"
                value={positionSizePct}
                onChange={(e) => setPositionSizePct(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="profile-objective">{t("profiles_field_objective")}</Label>
              <Textarea
                id="profile-objective"
                placeholder={t("profiles_objective_placeholder")}
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={createProfile.isPending} className="self-start">
              {createProfile.isPending ? t("profiles_submit_pending") : t("profiles_submit")}
            </Button>
          </form>
      </Panel>

      {isLoading && <p className="text-sm text-muted-foreground">{t("profiles_loading")}</p>}
      {isError && <p className="text-sm text-destructive">{t("profiles_error")}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {profiles?.map((p) => (
          <Panel
            key={p.id}
            color="var(--accent-green)"
            title={
              <span className="flex w-full items-center justify-between normal-case tracking-normal text-sm font-bold text-[var(--text-primary)]">
                {p.name}
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("profiles_delete_aria")}
                  onClick={() => deleteProfile.mutate(p.id)}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </span>
            }
          >
            <div className="flex flex-col gap-1 text-sm text-muted-foreground">
              <div>{t("profiles_card_risk", { value: p.risk_tolerance || "—" })}</div>
              <div>{t("profiles_card_horizon", { value: p.investment_horizon || "—" })}</div>
              <div>{t("profiles_card_size", { value: p.position_size_pct })}</div>
              <div>{t("profiles_card_objective", { value: p.objective || "—" })}</div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  )
}
