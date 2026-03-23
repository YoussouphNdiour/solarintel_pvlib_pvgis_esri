import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDeleteProject } from '@/hooks/useProjects'
import type { Project } from '@/types/api'

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat('fr-SN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(new Date(iso))
}

// ── ProjectCard ───────────────────────────────────────────────────────────────

interface ProjectCardProps {
  project: Project
}

export default function ProjectCard({ project }: ProjectCardProps) {
  const navigate = useNavigate()
  const deleteProject = useDeleteProject()
  const [showConfirm, setShowConfirm] = useState(false)

  const handleOpen = () => {
    navigate(`/projects/${project.id}`)
  }

  const handleDeleteConfirm = () => {
    deleteProject.mutate(project.id, {
      onSuccess: () => setShowConfirm(false),
    })
  }

  return (
    <article className="project-card group relative flex flex-col rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-900 line-clamp-1">{project.name}</h3>
        <span className="shrink-0 rounded-full bg-solar-100 px-2 py-0.5 text-xs font-medium text-solar-700">
          PV
        </span>
      </div>

      {/* Description */}
      {project.description !== null && (
        <p className="mt-1 text-sm text-gray-500 line-clamp-2">{project.description}</p>
      )}

      {/* Location */}
      <div className="mt-3 flex items-center gap-1.5 text-xs text-gray-500">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
        </svg>
        {project.address !== null ? (
          <span className="truncate">{project.address}</span>
        ) : (
          <span className="font-mono">
            {project.latitude.toFixed(4)}, {project.longitude.toFixed(4)}
          </span>
        )}
      </div>

      {/* Date */}
      <div className="mt-1 flex items-center gap-1.5 text-xs text-gray-400">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        <span>Créé le {formatDate(project.createdAt)}</span>
      </div>

      {/* Actions */}
      <div className="mt-4 flex gap-2">
        <button
          type="button"
          onClick={handleOpen}
          className="flex-1 rounded-lg bg-solar-500 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-solar-600 focus:outline-none focus:ring-2 focus:ring-solar-500 focus:ring-offset-1"
          aria-label={`Ouvrir le projet ${project.name}`}
        >
          Ouvrir
        </button>
        <button
          type="button"
          onClick={() => setShowConfirm(true)}
          className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-400 focus:ring-offset-1"
          aria-label={`Supprimer le projet ${project.name}`}
        >
          Supprimer
        </button>
      </div>

      {/* Delete confirmation dialog */}
      {showConfirm && (
        <div
          className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-xl bg-white/95 p-6 text-center backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby={`confirm-delete-${project.id}`}
        >
          <p id={`confirm-delete-${project.id}`} className="font-semibold text-gray-900">
            Supprimer ce projet ?
          </p>
          <p className="mt-1 text-sm text-gray-500">
            Cette action est irréversible.
          </p>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => setShowConfirm(false)}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Annuler
            </button>
            <button
              type="button"
              onClick={handleDeleteConfirm}
              disabled={deleteProject.isPending}
              className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
              aria-label="Confirmer la suppression"
            >
              {deleteProject.isPending ? 'Suppression...' : 'Supprimer'}
            </button>
          </div>
        </div>
      )}
    </article>
  )
}
