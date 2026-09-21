import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { builtinReasonDescriptions, translations, type TranslationKey } from "@/i18n/translations"

export type Lang = "en" | "th"

const STORAGE_KEY = "lang"

interface LanguageContextValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: TranslationKey | (string & {}), vars?: Record<string, string | number>) => string
  // For the 3 built-in reasons' descriptions (data from the backend, not a
  // dictionary key) -- falls back to `fallback` (the raw description,
  // e.g. a custom reason's own free text) when reasonKey isn't a built-in.
  tReason: (reasonKey: string | null | undefined, fallback: string) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

function readStoredLang(): Lang {
  if (typeof window === "undefined") return "en"
  const stored = window.localStorage.getItem(STORAGE_KEY)
  return stored === "th" || stored === "en" ? stored : "en"
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (match, name) => {
    return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match
  })
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readStoredLang())

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, lang)
    } catch {
      // ignore storage failures (e.g. private browsing)
    }
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
  }, [])

  const t = useCallback(
    (key: TranslationKey | (string & {}), vars?: Record<string, string | number>) => {
      const dict = translations[lang]
      const value = dict[key as TranslationKey]
      if (value === undefined) {
        if (import.meta.env.DEV) {
          console.warn(`[i18n] Missing translation key "${key}" for lang "${lang}"`)
        }
        return interpolate(key, vars)
      }
      return interpolate(value, vars)
    },
    [lang],
  )

  const tReason = useCallback(
    (reasonKey: string | null | undefined, fallback: string) => {
      const entry = reasonKey ? builtinReasonDescriptions[reasonKey] : undefined
      return entry ? entry[lang] : fallback
    },
    [lang],
  )

  const value = useMemo(() => ({ lang, setLang, t, tReason }), [lang, setLang, t, tReason])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useTranslation() {
  const ctx = useContext(LanguageContext)
  if (!ctx) {
    throw new Error("useTranslation must be used within a LanguageProvider")
  }
  return ctx
}
