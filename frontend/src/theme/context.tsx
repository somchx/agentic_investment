import { createContext, useContext, useState, useEffect, type ReactNode } from "react"

type Theme = "dark" | "light"

const ThemeContext = createContext<{ theme: Theme; toggle: () => void }>({
  theme: "light",
  toggle: () => {},
})

export const useTheme = () => useContext(ThemeContext)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return localStorage.getItem("reasoncheck.theme.v2") === "dark" ? "dark" : "light"
    } catch {
      return "light"
    }
  })

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme)
    try {
      localStorage.setItem("reasoncheck.theme.v2", theme)
    } catch {
      // ignore storage errors (private browsing, etc.)
    }
  }, [theme])

  return (
    <ThemeContext.Provider
      value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}
    >
      {children}
    </ThemeContext.Provider>
  )
}
