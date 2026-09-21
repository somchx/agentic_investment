import { useState, type FormEvent } from "react"
import { Trash2 } from "lucide-react"
import { Panel } from "@/components/ui/panel"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import { useCreateProfile, useDeleteProfile, useProfiles } from "@/hooks/use-profiles"
import { getApiErrorMessage } from "@/api/client"
import { useTranslation } from "@/i18n/context"

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
        <p className="max-w-2xl text-sm text-muted-foreground">
          {t("profiles_intro")}
        </p>
      </div>

      <Panel
        title={t("profiles_new_title")}
        description={t("profiles_new_description")}
        color="var(--accent-purple)"
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
