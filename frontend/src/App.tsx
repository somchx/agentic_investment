import { lazy } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter, Navigate, Route, Routes, useSearchParams } from "react-router-dom"
import { AuthProvider } from "@/hooks/use-auth"
import { AppLayout } from "@/components/app-layout"
import { ProtectedRoute, RedirectIfAuthenticated } from "@/components/protected-route"
import { AuthPage } from "@/pages/auth-page"

// Each page is its own chunk, so the first load only downloads the page being opened.
const DashboardPage = lazy(() => import("@/pages/dashboard-page").then((m) => ({ default: m.DashboardPage })))
const ScreenerPage = lazy(() => import("@/pages/screener-page").then((m) => ({ default: m.ScreenerPage })))
const AgentPage = lazy(() => import("@/pages/agent-page").then((m) => ({ default: m.AgentPage })))
const UserProfilePage = lazy(() => import("@/pages/user-profile-page").then((m) => ({ default: m.UserProfilePage })))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30 * 1000,
    },
  },
})

// The Portfolio page moved into the dashboard's holdings modal; keep old links
// (bookmarks, ?ticker= deep links) working by opening that modal instead.
function PortfolioRedirect() {
  const [params] = useSearchParams()
  const ticker = params.get("ticker")
  return <Navigate to={ticker ? `/?holding=${encodeURIComponent(ticker)}` : "/?holding="} replace />
}

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
                <Route path="/portfolio" element={<PortfolioRedirect />} />
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
