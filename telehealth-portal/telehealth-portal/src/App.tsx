// src/App.tsx
// ──────────────────────────────────────────────────────────────
// Central routing definition.
//
// Route tree:
//   /                   → redirect to /login
//   /login              → LoginPage (public)
//   /                   → ProtectedRoute (requires auth)
//     /dashboard        → DashboardPage  (inside AppLayout)
//     /cases/:caseId    → CaseDetailPage (inside AppLayout)
// ──────────────────────────────────────────────────────────────

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { CasesProvider } from "./context/CasesContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AppLayout from "./components/layout/AppLayout";
import LoginPage from "./pages/LoginPage";
import LandingPage from "./pages/LandingPage";
import DashboardPage from "./pages/DashboardPage";
import CaseDetailPage from "./pages/CaseDetailPage";

export default function App() {
  return (
    <BrowserRouter>
      {/*
        Provider order matters:
        AuthProvider must wrap CasesProvider because CasesProvider
        (and everything below it) may eventually need auth state.
      */}
      <AuthProvider>
        <CasesProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/login" element={<LoginPage />} />

            {/* Protected routes — rendered inside AppLayout shell */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/cases/:caseId" element={<CaseDetailPage />} />
              </Route>
            </Route>

            {/* Default redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </CasesProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
