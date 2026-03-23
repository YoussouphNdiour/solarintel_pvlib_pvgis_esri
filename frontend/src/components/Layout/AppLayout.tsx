import { Outlet } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { useLogout } from '@/hooks/useAuth'
import Sidebar from './Sidebar'

// ── Role badge colours ────────────────────────────────────────────────────────

const roleBadgeClass: Record<string, string> = {
  admin: 'bg-red-100 text-red-700',
  commercial: 'bg-blue-100 text-blue-700',
  technicien: 'bg-green-100 text-green-700',
  client: 'bg-gray-100 text-gray-700',
}

// ── Hamburger icon ────────────────────────────────────────────────────────────

function IconMenu() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  )
}

function IconClose() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function IconLogout() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  )
}

// ── Avatar initials ───────────────────────────────────────────────────────────

function getInitials(name: string | null | undefined, email: string): string {
  if (name != null && name.trim().length > 0) {
    const parts = name.trim().split(' ')
    const first = parts[0]?.[0] ?? ''
    const last = parts[1]?.[0] ?? ''
    return (first + last).toUpperCase()
  }
  return email.slice(0, 2).toUpperCase()
}

// ── AppLayout component ───────────────────────────────────────────────────────

export default function AppLayout() {
  const { user } = useAuthStore()
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useUIStore()
  const logout = useLogout()

  const badgeClass =
    user !== null
      ? (roleBadgeClass[user.role] ?? 'bg-gray-100 text-gray-700')
      : 'bg-gray-100 text-gray-700'

  const initials =
    user !== null ? getInitials(user.fullName, user.email) : '??'

  return (
    <div className="app-layout flex h-screen overflow-hidden bg-gray-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <Sidebar onClose={() => setSidebarOpen(false)} />

      {/* Main content */}
      <div className="app-main flex flex-1 flex-col overflow-hidden">
        {/* Top header */}
        <header className="app-header flex h-16 items-center justify-between border-b border-gray-200 bg-white px-4 shadow-sm lg:px-6">
          <div className="flex items-center gap-3">
            {/* Hamburger toggle */}
            <button
              type="button"
              onClick={toggleSidebar}
              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 lg:hidden"
              aria-label={sidebarOpen ? 'Fermer la navigation' : 'Ouvrir la navigation'}
            >
              {sidebarOpen ? <IconClose /> : <IconMenu />}
            </button>
            {/* Desktop sidebar toggle */}
            <button
              type="button"
              onClick={toggleSidebar}
              className="hidden rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700 lg:flex"
              aria-label={sidebarOpen ? 'Réduire la barre latérale' : 'Agrandir la barre latérale'}
            >
              <IconMenu />
            </button>
            <h1 className="hidden text-lg font-semibold text-gray-900 sm:block">
              SolarIntel v2
            </h1>
          </div>

          {/* User section */}
          <div className="flex items-center gap-3">
            {user !== null && (
              <span
                className={`hidden rounded-full px-2.5 py-0.5 text-xs font-medium capitalize sm:inline-flex ${badgeClass}`}
              >
                {user.role}
              </span>
            )}

            {/* Avatar */}
            <div
              className="flex h-9 w-9 items-center justify-center rounded-full bg-solar-500 text-sm font-semibold text-white"
              title={user?.email ?? ''}
              aria-label={`Utilisateur : ${user?.fullName ?? user?.email ?? 'Inconnu'}`}
            >
              {initials}
            </div>

            {/* Logout */}
            <button
              type="button"
              onClick={logout}
              className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              aria-label="Se déconnecter"
            >
              <IconLogout />
              <span className="hidden sm:inline">Déconnexion</span>
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className="app-content flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>

      {/* Global toast notifications */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { fontFamily: 'Inter, system-ui, sans-serif' },
          success: { style: { background: '#f0fdf4', color: '#166534', border: '1px solid #bbf7d0' } },
          error: { style: { background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' } },
        }}
      />
    </div>
  )
}
