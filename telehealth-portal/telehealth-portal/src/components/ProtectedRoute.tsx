// src/components/ProtectedRoute.tsx
// ──────────────────────────────────────────────────────────────
// Route guard: redirects to /login if the doctor is not
// authenticated. Wrap any route that requires login.
// ──────────────────────────────────────────────────────────────

import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    // Redirect to login, preserving the intended URL in state
    return <Navigate to="/login" replace />;
  }

  // Render the matched child route
  return <Outlet />;
}
