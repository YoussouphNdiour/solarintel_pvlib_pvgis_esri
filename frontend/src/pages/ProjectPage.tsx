import { useNavigate, useParams } from 'react-router-dom'
import { MapPin, Calendar, PlayCircle, Eye, Zap, BarChart2 } from 'lucide-react'
import { useProject } from '@/hooks/useProjects'
import { useSimulations } from '@/hooks/useSimulations'
import { useProjectStore } from '@/stores/projectStore'
import { formatKwh, formatKwc } from '@/utils/format'
import type { Simulation } from '@/types/api'

// ── Status helpers ────────────────────────────────────────────────────────────

const STATUS_STYLE: Record<Simulation['status'], string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  running: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
}
const STATUS_LABEL: Record<Simulation['status'], string> = {
  pending: 'En attente', running: 'En cours', completed: 'Terminée', failed: 'Échouée',
}

// ── Simulation history row ────────────────────────────────────────────────────

function SimRow({ sim, onView }: { sim: Simulation; onView: (id: string) => void }) {
  const date = new Date(sim.createdAt).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
  return (
    <li className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl border border-gray-200 bg-white hover:border-solar-300 hover:bg-solar-50/40 transition-colors">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-solar-100 flex items-center justify-center shrink-0">
          <Zap size={16} className="text-solar-600" aria-hidden="true" />
        </div>
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-900">{formatKwc(sim.peakKwc)}</span>
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_STYLE[sim.status]}`}>
              {STATUS_LABEL[sim.status]}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1"><BarChart2 size={11} aria-hidden="true" />{formatKwh(sim.annualKwh)} / an</span>
            <span className="flex items-center gap-1"><Calendar size={11} aria-hidden="true" />{date}</span>
          </div>
        </div>
      </div>
      <button type="button" onClick={() => onView(sim.id)} aria-label={`Voir la simulation du ${date}`}
        className="self-end sm:self-auto flex items-center gap-1.5 text-xs font-medium text-solar-700 hover:text-solar-800 bg-solar-50 hover:bg-solar-100 border border-solar-200 rounded-lg px-3 py-1.5 transition-colors">
        <Eye size={13} aria-hidden="true" />Voir
      </button>
    </li>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ProjectPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const setCurrentProject = useProjectStore((s) => s.setCurrentProject)

  const { data: project, isLoading: projectLoading, isError: projectError } = useProject(id)
  const { data: simsPage, isLoading: simsLoading } = useSimulations(id)
  const simulations = simsPage?.items.slice(0, 5) ?? []

  function handleRunSimulation() {
    if (project !== undefined) setCurrentProject(project)
    void navigate(`/simulate?projectId=${id}`)
  }

  if (projectLoading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <div className="inline-block w-8 h-8 border-4 border-solar-400 border-t-transparent rounded-full animate-spin" aria-label="Chargement du projet" />
        <p className="mt-3 text-sm text-gray-500">Chargement du projet...</p>
      </div>
    )
  }

  if (projectError || project === undefined) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center space-y-3">
        <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mx-auto">
          <span className="text-red-500 text-xl font-bold">!</span>
        </div>
        <h2 className="text-base font-semibold text-gray-900">Projet introuvable</h2>
        <p className="text-sm text-gray-500">Impossible de charger ce projet. Vérifiez l'identifiant ou revenez au tableau de bord.</p>
        <button type="button" onClick={() => void navigate('/dashboard')}
          className="mt-2 rounded-xl bg-solar-500 hover:bg-solar-600 text-white font-semibold px-5 py-2 text-sm transition-colors">
          Retour au tableau de bord
        </button>
      </div>
    )
  }

  const createdAt = new Date(project.createdAt).toLocaleDateString('fr-FR', { day: '2-digit', month: 'long', year: 'numeric' })

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Project header */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
            {project.description !== null && <p className="text-sm text-gray-500">{project.description}</p>}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
              <span className="flex items-center gap-1.5">
                <MapPin size={14} className="text-solar-500" aria-hidden="true" />
                {project.address ?? `${project.latitude.toFixed(4)}, ${project.longitude.toFixed(4)}`}
              </span>
              <span className="flex items-center gap-1.5">
                <Calendar size={14} className="text-gray-400" aria-hidden="true" />
                Créé le {createdAt}
              </span>
            </div>
          </div>
          <button type="button" onClick={handleRunSimulation}
            className="shrink-0 flex items-center gap-2 rounded-xl bg-solar-500 hover:bg-solar-600 text-white font-semibold px-5 py-2.5 text-sm transition-colors">
            <PlayCircle size={16} aria-hidden="true" />Lancer une simulation
          </button>
        </div>
      </div>

      {/* Simulation history */}
      <section aria-label="Historique des simulations">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-900">Dernières simulations</h2>
          {simsPage !== undefined && simsPage.total > 5 && (
            <span className="text-xs text-gray-500">Affichage 5 / {simsPage.total}</span>
          )}
        </div>

        {simsLoading && (
          <div className="text-center py-8">
            <div className="inline-block w-6 h-6 border-4 border-solar-400 border-t-transparent rounded-full animate-spin" aria-label="Chargement des simulations" />
          </div>
        )}

        {!simsLoading && simulations.length === 0 && (
          <div className="rounded-2xl border-2 border-dashed border-gray-200 py-12 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center mx-auto">
              <BarChart2 size={22} className="text-gray-400" aria-hidden="true" />
            </div>
            <p className="text-sm font-medium text-gray-600">Aucune simulation pour ce projet</p>
            <p className="text-xs text-gray-400">Lancez votre première simulation pour voir les résultats ici.</p>
            <button type="button" onClick={handleRunSimulation}
              className="mt-2 inline-flex items-center gap-1.5 rounded-xl bg-solar-500 hover:bg-solar-600 text-white font-semibold px-5 py-2 text-sm transition-colors">
              <PlayCircle size={14} aria-hidden="true" />Lancer une simulation
            </button>
          </div>
        )}

        {!simsLoading && simulations.length > 0 && (
          <ul className="space-y-2" aria-label="Liste des simulations">
            {simulations.map((sim) => (
              <SimRow key={sim.id} sim={sim}
                onView={(simId) => void navigate(`/simulate?simulationId=${simId}`)} />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
