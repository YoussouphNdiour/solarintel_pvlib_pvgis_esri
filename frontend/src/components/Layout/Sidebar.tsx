import { NavLink } from 'react-router-dom'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'

// ── Nav item definition ───────────────────────────────────────────────────────

interface NavItem {
  label: string
  to: string
  icon: React.ReactNode
  adminOnly?: boolean
}

// ── Inline SVG icons (lucide-style) ──────────────────────────────────────────

function IconGrid() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  )
}

function IconZap() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  )
}

function IconFolder() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
    </svg>
  )
}

function IconBarChart() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
    </svg>
  )
}

function IconActivity() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  )
}

function IconSettings() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14" />
    </svg>
  )
}

function IconWrench() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  )
}

// ── Nav items ─────────────────────────────────────────────────────────────────

const navItems: NavItem[] = [
  { label: 'Tableau de bord', to: '/dashboard', icon: <IconGrid /> },
  { label: 'Nouvelle simulation', to: '/simulate', icon: <IconZap /> },
  { label: 'Projets', to: '/projects', icon: <IconFolder /> },
  { label: 'Rapports', to: '/reports', icon: <IconBarChart /> },
  { label: 'Équipements', to: '/equipment', icon: <IconWrench /> },
  { label: 'Monitoring', to: '/monitoring', icon: <IconActivity /> },
  { label: 'Admin', to: '/admin', icon: <IconSettings />, adminOnly: true },
]

// ── Sidebar component ─────────────────────────────────────────────────────────

interface SidebarProps {
  onClose?: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const { user } = useAuthStore()
  const { sidebarOpen } = useUIStore()

  const visibleItems = navItems.filter(
    (item) => !item.adminOnly || user?.role === 'admin',
  )

  return (
    <aside
      className={`sidebar fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-gray-900 transition-transform duration-300 lg:static lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}
      aria-label="Navigation principale"
    >
      {/* Logo area */}
      <div className="sidebar-logo flex h-16 items-center gap-3 border-b border-gray-700 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-solar-500">
          <span className="text-sm font-bold text-white">SI</span>
        </div>
        <span className="text-lg font-bold text-white">SolarIntel v2</span>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav flex-1 overflow-y-auto px-3 py-4" role="navigation">
        <ul className="space-y-1" role="list">
          {visibleItems.map((item) => (
            <li key={item.to} role="listitem">
              <NavLink
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  `sidebar-nav-link flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-solar-600 text-white'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`
                }
                aria-label={item.label}
              >
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Footer: user role info */}
      {user !== null && (
        <div className="sidebar-footer border-t border-gray-700 px-4 py-3">
          <p className="text-xs text-gray-500">Connecté en tant que</p>
          <p className="mt-0.5 text-sm font-medium capitalize text-gray-300">
            {user.role}
          </p>
        </div>
      )}
    </aside>
  )
}
