import { useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { useProjects } from '@/hooks/useProjects'
import ProjectCard from '@/components/Dashboard/ProjectCard'
import NewProjectModal from '@/components/Dashboard/NewProjectModal'

// ── Skeleton ──────────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-gray-200 bg-white p-5">
      <div className="mb-3 h-5 w-2/3 rounded bg-gray-200" />
      <div className="mb-2 h-3 w-full rounded bg-gray-100" />
      <div className="mb-4 h-3 w-4/5 rounded bg-gray-100" />
      <div className="flex gap-2">
        <div className="h-9 flex-1 rounded-lg bg-gray-200" />
        <div className="h-9 w-24 rounded-lg bg-gray-100" />
      </div>
    </div>
  )
}

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
}

function StatCard({ label, value, icon }: StatCardProps) {
  return (
    <div className="stat-card flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 shadow-sm">
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-solar-100 text-solar-600">
        {icon}
      </div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="mt-0.5 text-2xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyProjects({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-gray-300 bg-white py-16 text-center">
      <div className="mb-4 text-5xl" aria-hidden="true">☀️</div>
      <h3 className="text-lg font-semibold text-gray-900">Aucun projet pour l'instant</h3>
      <p className="mt-2 max-w-sm text-sm text-gray-500">
        Créez votre premier projet de dimensionnement PV pour démarrer vos simulations.
      </p>
      <button
        type="button"
        onClick={onNew}
        className="mt-6 rounded-lg bg-solar-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-2"
        aria-label="Créer un nouveau projet"
      >
        Créer mon premier projet
      </button>
    </div>
  )
}

// ── DashboardPage ─────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [modalOpen, setModalOpen] = useState(false)

  const {
    data,
    isLoading,
    isError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useProjects()

  const allProjects = data?.pages.flatMap((page) => page.items) ?? []
  const totalProjects = data?.pages[0]?.total ?? 0

  const greeting = user?.fullName !== null && user?.fullName !== undefined
    ? `Bonjour, ${user.fullName.split(' ')[0]} 👋`
    : `Bonjour 👋`

  return (
    <div className="dashboard space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{greeting}</h1>
          <p className="mt-1 text-sm text-gray-500">
            Bienvenue sur votre tableau de bord SolarIntel v2
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="flex items-center gap-2 rounded-lg bg-solar-500 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-2"
          aria-label="Créer un nouveau projet"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Nouveau projet
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Projets totaux"
          value={isLoading ? '—' : totalProjects}
          icon={
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
            </svg>
          }
        />
        <StatCard
          label="Simulations réalisées"
          value="—"
          icon={
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
          }
        />
        <StatCard
          label="Compte"
          value={user?.role ?? '—'}
          icon={
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
            </svg>
          }
        />
      </div>

      {/* Projects section */}
      <section aria-labelledby="projects-heading">
        <h2 id="projects-heading" className="mb-4 text-lg font-semibold text-gray-900">
          Mes projets
        </h2>

        {/* Error state */}
        {isError && (
          <div className="rounded-xl bg-red-50 px-5 py-4 text-sm text-red-700" role="alert">
            Erreur lors du chargement des projets. Veuillez rafraîchir la page.
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && allProjects.length === 0 && (
          <EmptyProjects onNew={() => setModalOpen(true)} />
        )}

        {/* Projects grid */}
        {!isLoading && allProjects.length > 0 && (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {allProjects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>

            {/* Load more */}
            {hasNextPage === true && (
              <div className="mt-6 flex justify-center">
                <button
                  type="button"
                  onClick={() => void fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className="rounded-lg border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-60"
                  aria-label="Charger plus de projets"
                >
                  {isFetchingNextPage ? 'Chargement...' : 'Charger plus'}
                </button>
              </div>
            )}
          </>
        )}
      </section>

      {/* New project modal */}
      <NewProjectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
