import { lazy } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/use-auth"
import { AppLayout } from "@/components/app-layout"
import { ProtectedRoute, RedirectIfAuthenticated } from "@/components/protected-route"
import { AuthPage } from "@/pages/auth-page"

// Each page is its own chunk, so the first load only downloads the page being opened.
const DashboardPage = lazy(() => import("@/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })))
const ScreenerPage = lazy(() => import("@/pages/screener-page").then((m) => ({ default: m.ScreenerPage })))
const AgentPage = lazy(() => import("@/pages/agent-page").then((m) => ({ default: m.AgentPage })))
const UserProfilePage = lazy(() => import("@/pages/user-profile-page").then((m) => ({ default: m.UserProfilePage })))

const PortfolioPage = lazy(() => import('@/pages/portfolio-page').then(m=>({default:m.PortfolioPage})))
const CompaniesPage = lazy(() => import('@/pages/companies-page').then(m=>({default:m.CompaniesPage})))
const ReportsPage = lazy(() => import('@/pages/reports-page').then(m=>({default:m.ReportsPage})))

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
                <Route path="/companies" element={<CompaniesPage />} />
                <Route path="/watchlist" element={<CompaniesPage favoritesOnly />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/agent" element={<AgentPage />} />
                <Route path="/user" element={<UserProfilePage />} />
                <Route path="/user/change-password" element={<Navigate to="/user" replace />} />
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
