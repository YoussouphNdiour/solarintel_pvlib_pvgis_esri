// ── ReportCard ────────────────────────────────────────────────────────────────
// A single report list item with status badge and download actions.

import { FileDown, ExternalLink, AlertTriangle, RotateCcw } from 'lucide-react'
import { useDownloadReport, useDownloadHtmlReport } from '@/hooks/useReports'
import { formatRelativeTime } from '@/utils/format'
import type { ReportStatus, ReportStatusResponse } from '@/types/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReportCardProps {
  report: ReportStatusResponse
  projectName: string
  simulationDate: string
  onRetry?: (simulationId: string) => void
}

// ── Status badge ──────────────────────────────────────────────────────────────

interface BadgeProps { status: ReportStatus }

function StatusBadge({ status }: BadgeProps) {
  const map: Record<ReportStatus, { label: string; className: string; pulse: boolean }> = {
    pending:    { label: 'En attente',   className: 'bg-gray-100 text-gray-600 border-gray-200',          pulse: false },
    generating: { label: 'Génération…',  className: 'bg-solar-100 text-solar-700 border-solar-200',       pulse: true  },
    ready:      { label: 'Prêt',         className: 'bg-green-100 text-green-700 border-green-200',        pulse: false },
    failed:     { label: 'Erreur',       className: 'bg-red-100 text-red-700 border-red-200',              pulse: false },
  }

  const { label, className, pulse } = map[status]

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${className}`}
    >
      {pulse && (
        <span
          className="w-1.5 h-1.5 rounded-full bg-solar-400 animate-pulse"
          aria-hidden="true"
        />
      )}
      {status === 'failed' && (
        <AlertTriangle size={10} aria-hidden="true" />
      )}
      {label}
    </span>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ReportCard({
  report,
  projectName,
  simulationDate,
  onRetry,
}: ReportCardProps) {
  const downloadPdf  = useDownloadReport(report.id)
  const downloadHtml = useDownloadHtmlReport()

  const isReady    = report.status === 'ready'
  const isFailed   = report.status === 'failed'

  return (
    <article
      className="rounded-xl border border-gray-200 bg-white p-4 flex flex-col sm:flex-row sm:items-center gap-4"
      aria-label={`Rapport — ${projectName}`}
    >
      {/* Left: metadata */}
      <div className="flex-1 min-w-0 space-y-1">
        <p className="text-sm font-semibold text-gray-900 truncate">{projectName}</p>
        <p className="text-xs text-gray-500">
          Simulation du {new Date(simulationDate).toLocaleDateString('fr-FR', {
            day: 'numeric', month: 'long', year: 'numeric',
          })}
        </p>
        <p className="text-xs text-gray-400">
          Créé {formatRelativeTime(report.createdAt)}
        </p>
        {isFailed && (
          <p className="text-xs text-red-600 font-medium">Erreur de génération</p>
        )}
      </div>

      {/* Center: status badge */}
      <StatusBadge status={report.status} />

      {/* Right: actions */}
      <div className="flex flex-col sm:flex-row gap-2 shrink-0">
        {isReady && (
          <>
            <button
              type="button"
              onClick={() =>
                downloadPdf.mutate({
                  reportId: report.id,
                  filename: `rapport-${report.id.slice(0, 8)}.pdf`,
                })
              }
              disabled={downloadPdf.isPending}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-solar-500 hover:bg-solar-600 disabled:opacity-60 text-white font-semibold px-3 py-2 text-xs transition-colors shadow-sm"
              aria-label="Télécharger le rapport PDF"
            >
              <FileDown size={13} aria-hidden="true" />
              PDF
            </button>
            <button
              type="button"
              onClick={() => downloadHtml.mutate(report.id)}
              disabled={downloadHtml.isPending}
              className="flex items-center justify-center gap-1.5 rounded-lg border border-solar-300 bg-solar-50 hover:bg-solar-100 disabled:opacity-60 text-solar-700 font-semibold px-3 py-2 text-xs transition-colors"
              aria-label="Ouvrir le rapport HTML interactif"
            >
              <ExternalLink size={13} aria-hidden="true" />
              HTML
            </button>
          </>
        )}

        {isFailed && onRetry !== undefined && (
          <button
            type="button"
            onClick={() => onRetry(report.simulationId)}
            className="flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 text-red-700 font-semibold px-3 py-2 text-xs transition-colors"
            aria-label="Réessayer la génération du rapport"
          >
            <RotateCcw size={13} aria-hidden="true" />
            Réessayer
          </button>
        )}
      </div>
    </article>
  )
}
