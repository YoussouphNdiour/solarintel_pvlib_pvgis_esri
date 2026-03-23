// ── MonitoringPage ────────────────────────────────────────────────────────────
// Real-time monitoring dashboard — MON-001.

import { useMemo, useState } from 'react'
import { useProjects } from '@/hooks/useProjects'
import {
  useMonitoringStats,
  useMonitoringWebSocket,
  useMonthlyComparison,
  useMonitoringHistory,
} from '@/hooks/useMonitoring'
import ProductionKPICards from '@/components/Monitoring/ProductionKPICards'
import RealtimeProductionChart from '@/components/Monitoring/RealtimeProductionChart'
import MonthlyComparisonChart from '@/components/Monitoring/MonthlyComparisonChart'
import AlertsPanel from '@/components/Monitoring/AlertsPanel'
import LatestReadingsTable from '@/components/Monitoring/LatestReadingsTable'
import ConnectionStatus from '@/components/Monitoring/ConnectionStatus'
import type { Project } from '@/types/api'

// ── Project selector ──────────────────────────────────────────────────────────

function ProjectSelector({
  projects,
  selectedId,
  onChange,
}: {
  projects: Project[]
  selectedId: string
  onChange: (id: string) => void
}) {
  if (projects.length <= 1) return null
  return (
    <select
      value={selectedId}
      onChange={(e) => onChange(e.target.value)}
      className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-solar-500"
      aria-label="Sélectionner un projet"
    >
      {projects.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name}
        </option>
      ))}
    </select>
  )
}

// ── Skeleton cards ────────────────────────────────────────────────────────────

function KPISkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-28 animate-pulse rounded-xl bg-gray-100" />
      ))}
    </div>
  )
}

// ── Dashboard body ────────────────────────────────────────────────────────────

function MonitoringDashboard({ projectId }: { projectId: string }) {
  const {
    stats: wsStats,
    readings,
    alerts,
    isConnected,
    reconnectAttempts,
    forceReconnect,
  } = useMonitoringWebSocket(projectId)

  const { data: httpStats, isLoading: statsLoading } = useMonitoringStats(projectId)
  const { data: monthlyData = [] } = useMonthlyComparison(projectId)
  const { data: historyPages } = useMonitoringHistory(projectId)

  const historyReadings = useMemo(
    () => historyPages?.pages.flatMap((p) => p.items) ?? [],
    [historyPages],
  )

  // WS readings prepended over paginated history, capped at 100
  const allReadings = useMemo(
    () => [...readings, ...historyReadings].slice(0, 100),
    [readings, historyReadings],
  )

  const stats = wsStats ?? httpStats ?? null

  return (
    <>
      {/* Connection pill row */}
      <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
        <ConnectionStatus
          isConnected={isConnected}
          reconnectAttempts={reconnectAttempts}
          onReconnect={forceReconnect}
        />
        {stats?.lastReadingAt && (
          <span className="text-xs text-gray-400">
            Dernière lecture:{' '}
            {new Intl.DateTimeFormat('fr-SN', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            }).format(new Date(stats.lastReadingAt))}
          </span>
        )}
      </div>

      <div className="space-y-5">
        {/* KPI Cards */}
        {stats !== null ? (
          <ProductionKPICards stats={stats} />
        ) : statsLoading ? (
          <KPISkeleton />
        ) : (
          <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-400">
            Aucune donnée de production disponible pour ce projet.
          </div>
        )}

        {/* Realtime line chart */}
        <RealtimeProductionChart
          readings={allReadings}
          isConnected={isConnected}
          reconnectAttempts={reconnectAttempts}
          onReconnect={forceReconnect}
        />

        {/* Monthly bar+line comparison */}
        <MonthlyComparisonChart data={monthlyData} />

        {/* Alerts + Readings table */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <AlertsPanel alerts={alerts} />
          <LatestReadingsTable readings={allReadings} />
        </div>
      </div>
    </>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function MonitoringPage() {
  const { data: projectPages, isLoading: projectsLoading } = useProjects()

  const allProjects: Project[] = useMemo(
    () => projectPages?.pages.flatMap((p) => p.items) ?? [],
    [projectPages],
  )

  const [selectedProjectId, setSelectedProjectId] = useState<string>('')

  const effectiveProjectId =
    selectedProjectId.length > 0
      ? selectedProjectId
      : (allProjects[0]?.id ?? '')

  if (projectsLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div
          className="h-8 w-8 animate-spin rounded-full border-4 border-solar-300 border-t-solar-600"
          aria-label="Chargement..."
          role="status"
        />
      </div>
    )
  }

  if (allProjects.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-gray-500">
        <p className="text-sm">Aucun projet trouvé.</p>
        <p className="text-xs text-gray-400">
          Créez un projet pour accéder au monitoring.
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold text-gray-900">Monitoring</h1>
        <ProjectSelector
          projects={allProjects}
          selectedId={effectiveProjectId}
          onChange={setSelectedProjectId}
        />
      </div>

      {effectiveProjectId.length > 0 ? (
        <MonitoringDashboard projectId={effectiveProjectId} />
      ) : (
        <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-10 text-center text-sm text-gray-400">
          Sélectionnez un projet pour voir le monitoring.
        </div>
      )}
    </div>
  )
}
