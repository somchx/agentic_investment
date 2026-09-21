import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/use-auth"
import { AppLayout } from "@/components/app-layout"
import { ProtectedRoute, RedirectIfAuthenticated } from "@/components/protected-route"
import { AuthPage } from "@/pages/auth-page"
import { DashboardPage } from "@/pages/dashboard-page"
import { ScreenerPage } from "@/pages/screener-page"
import { PortfolioPage } from "@/pages/portfolio-page"
import { ProfilesPage } from "@/pages/profiles-page"
import { AgentPage } from "@/pages/agent-page"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30 * 1000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route
              path="/login"
              element={
                <RedirectIfAuthenticated>
                  <AuthPage />
                </RedirectIfAuthenticated>
              }
            />

            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="/screener" element={<ScreenerPage />} />
                <Route path="/portfolio" element={<PortfolioPage />} />
                <Route path="/profiles" element={<ProfilesPage />} />
                <Route path="/agent" element={<AgentPage />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
