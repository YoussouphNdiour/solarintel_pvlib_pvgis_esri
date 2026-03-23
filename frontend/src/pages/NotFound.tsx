import { Link } from 'react-router-dom'

// ── NotFound ──────────────────────────────────────────────────────────────────

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4 text-center">
      <div className="mb-6 text-7xl" aria-hidden="true">🔍</div>
      <h1 className="text-5xl font-bold text-gray-900">404</h1>
      <p className="mt-3 text-lg text-gray-500">Page introuvable</p>
      <p className="mt-2 max-w-sm text-sm text-gray-400">
        La page que vous recherchez n'existe pas ou a été déplacée.
      </p>
      <Link
        to="/dashboard"
        className="mt-8 rounded-lg bg-solar-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-2"
      >
        Retour au tableau de bord
      </Link>
    </div>
  )
}
