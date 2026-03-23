import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import type { UserRole } from '@/types/api'

// ── PrivateRoute ──────────────────────────────────────────────────────────────

interface PrivateRouteProps {
  requiredRoles?: UserRole[]
}

export default function PrivateRoute({ requiredRoles }: PrivateRouteProps) {
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()

  // Not authenticated → redirect to login with return path
  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        state={{ from: location }}
        replace
      />
    )
  }

  // Role check (if roles are specified)
  if (
    requiredRoles !== undefined &&
    requiredRoles.length > 0 &&
    user !== null &&
    !requiredRoles.includes(user.role)
  ) {
    return (
      <Navigate
        to="/dashboard"
        replace
      />
    )
  }

  return <Outlet />
}
