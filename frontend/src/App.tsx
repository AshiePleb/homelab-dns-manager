import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "@/context/auth";
import { ThemeProvider } from "@/context/theme";
import { Layout } from "@/components/layout";
import { LoginPage } from "@/pages/login";
import { OnboardingPage } from "@/pages/onboarding";
import { ServicesPage } from "@/pages/services";
import { DashboardPage } from "@/pages/dashboard";
import { DomainsPage } from "@/pages/domains";
import { RecordsPage } from "@/pages/records";
import { LogsPage } from "@/pages/logs";
import { SettingsPage } from "@/pages/settings";
import { CaddyPage } from "@/pages/caddy";
import { ApiKeysPage } from "@/pages/api-keys";

function LoadingScreen() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_credentials) return <Navigate to="/onboarding" replace />;
  return <>{children}</>;
}

function OnboardingRoute() {
  const { user, loading } = useAuth();
  if (loading) return <LoadingScreen />;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.must_change_credentials) return <Navigate to="/" replace />;
  return <OnboardingPage />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/onboarding" element={<OnboardingRoute />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="services" element={<ServicesPage />} />
        <Route path="domains" element={<DomainsPage />} />
        <Route path="records" element={<RecordsPage />} />
        <Route path="caddy" element={<CaddyPage />} />
        <Route path="api-keys" element={<ApiKeysPage />} />
        <Route path="logs" element={<LogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ThemeProvider>
          <AppRoutes />
        </ThemeProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
