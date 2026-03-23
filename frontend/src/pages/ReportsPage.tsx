// ── ReportsPage ───────────────────────────────────────────────────────────────
// Lists all generated reports grouped by project.

import { useMemo } from 'react'
import { FileText } from 'lucide-react'
import { useProjects } from '@/hooks/useProjects'
import { useReportsBySimulation } from '@/hooks/useReports'
import { useSimulations } from '@/hooks/useSimulations'
import ReportCard from '@/components/Report/ReportCard'
import { useCreateReport } from '@/hooks/useReports'
import type { Project, ReportStatusResponse, Simulation } from '@/types/api'

// ── Loading skeleton ───────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 animate-pulse">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-200 rounded w-2/3" />
          <div className="h-3 bg-gray-100 rounded w-1/2" />
          <div className="h-3 bg-gray-100 rounded w-1/3" />
        </div>
        <div className="h-6 w-20 bg-gray-100 rounded-full" />
        <div className="flex gap-2">
          <div className="h-8 w-16 bg-gray-100 rounded-lg" />
          <div className="h-8 w-16 bg-gray-100 rounded-lg" />
        </div>
      </div>
    </div>
  )
}

// ── Per-simulation report row ─────────────────────────────────────────────────
// Loads reports for a single simulation and renders them.

interface SimulationReportsProps {
  simulation: Simulation
  project: Project
}

function SimulationReports({ simulation, project }: SimulationReportsProps) {
  const { data: reports, isLoading } = useReportsBySimulation(simulation.id)
  const createReport = useCreateReport()

  function handleRetry(simId: string) {
    createReport.mutate({ simulationId: simId })
  }

  if (isLoading) {
    return <SkeletonCard />
  }

  if (reports === undefined || reports.length === 0) {
    return null
  }

  return (
    <>
      {reports.map((report: ReportStatusResponse) => (
        <ReportCard
          key={report.id}
          report={report}
          projectName={project.name}
          simulationDate={simulation.createdAt}
          onRetry={handleRetry}
        />
      ))}
    </>
  )
}

// ── Per-project section ───────────────────────────────────────────────────────

interface ProjectReportSectionProps {
  project: Project
}

function ProjectReportSection({ project }: ProjectReportSectionProps) {
  const { data: simulations, isLoading } = useSimulations(project.id)

  const items = useMemo(
    () => simulations?.items ?? [],
    [simulations],
  )

  if (isLoading) {
    return (
      <section aria-label={`Rapports — ${project.name}`} className="space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">{project.name}</h2>
        <SkeletonCard />
        <SkeletonCard />
      </section>
    )
  }

  if (items.length === 0) return null

  return (
    <section aria-label={`Rapports — ${project.name}`} className="space-y-2">
      <h2 className="text-sm font-semibold text-gray-700 px-1">{project.name}</h2>
      {items.map((sim) => (
        <SimulationReports key={sim.id} simulation={sim} project={project} />
      ))}
    </section>
  )
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <div className="w-14 h-14 rounded-2xl bg-solar-50 border border-solar-200 flex items-center justify-center">
        <FileText size={24} className="text-solar-400" aria-hidden="true" />
      </div>
      <div className="space-y-1">
        <p className="text-base font-semibold text-gray-700">
          Aucun rapport généré
        </p>
        <p className="text-sm text-gray-500">
          Lancez une simulation pour commencer
        </p>
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReportsPage() {
  const { data, isLoading, isError } = useProjects()

  const projects: Project[] = useMemo(() => {
    if (data === undefined) return []
    return data.pages.flatMap((page) => page.items)
  }, [data])

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      {/* Page header */}
      <header className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-solar-50 border border-solar-200 flex items-center justify-center">
          <FileText size={20} className="text-solar-600" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-gray-900">Mes Rapports</h1>
          <p className="text-sm text-gray-500">
            Rapports PDF et HTML générés pour vos simulations
          </p>
        </div>
      </header>

      {/* Error state */}
      {isError && (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          role="alert"
        >
          Impossible de charger les projets. Veuillez réessayer.
        </div>
      )}

      {/* Loading: project skeletons */}
      {isLoading && (
        <div className="space-y-6">
          {[1, 2].map((n) => (
            <section key={n} className="space-y-2">
              <div className="h-4 bg-gray-200 rounded w-32 animate-pulse" />
              <SkeletonCard />
              <SkeletonCard />
            </section>
          ))}
        </div>
      )}

      {/* Projects list */}
      {!isLoading && !isError && projects.length === 0 && <EmptyState />}

      {!isLoading && !isError && projects.length > 0 && (
        <div className="space-y-8">
          {projects.map((project) => (
            <ProjectReportSection key={project.id} project={project} />
          ))}
        </div>
      )}
    </div>
  )
}
