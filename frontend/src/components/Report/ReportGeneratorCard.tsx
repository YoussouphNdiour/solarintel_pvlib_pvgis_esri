// ── ReportGeneratorCard ───────────────────────────────────────────────────────
// Card displayed in SimulationResults to trigger + download PDF/HTML reports.

import { useState, useEffect, useRef } from 'react'
import {
  FileText,
  ExternalLink,
  RotateCcw,
  AlertTriangle,
  FileDown,
} from 'lucide-react'
import {
  useCreateReport,
  useReportStatus,
  useDownloadReport,
  useDownloadHtmlReport,
} from '@/hooks/useReports'
import { formatRelativeTime } from '@/utils/format'
import ReportStatusProgress from './ReportStatusProgress'
import WhatsAppSendButton from '@/components/Integration/WhatsAppSendButton'

// ── Types ─────────────────────────────────────────────────────────────────────

interface ReportGeneratorCardProps {
  simulationId: string
  hasAIAnalysis: boolean
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ReportGeneratorCard({
  simulationId,
  hasAIAnalysis,
}: ReportGeneratorCardProps) {
  const [reportId, setReportId] = useState<string | null>(null)
  const [clientName, setClientName]     = useState('')
  const [installerName, setInstallerName] = useState('')
  const [includeAI, setIncludeAI]       = useState(hasAIAnalysis)

  // Track elapsed seconds since generation started for time-remaining display.
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const createReport   = useCreateReport()
  const reportStatus   = useReportStatus(reportId)
  const downloadPdf    = useDownloadReport(reportId)
  const downloadHtml   = useDownloadHtmlReport()

  const status = reportStatus.data?.status ?? null
  const isGenerating = status === 'pending' || status === 'generating'

  // Start / stop elapsed timer alongside generation.
  useEffect(() => {
    if (isGenerating) {
      setElapsed(0)
      timerRef.current = setInterval(() => {
        setElapsed((s) => s + 1)
      }, 1_000)
    } else {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
        timerRef.current = null
      }
    }
    return () => {
      if (timerRef.current !== null) {
        clearInterval(timerRef.current)
      }
    }
  }, [isGenerating])

  function handleGenerate() {
    setElapsed(0)
    const payload: import('@/types/api').ReportRequest = { simulationId }
    const trimmedClient = clientName.trim()
    if (trimmedClient !== '') payload.clientName = trimmedClient
    const trimmedInstaller = installerName.trim()
    if (trimmedInstaller !== '') payload.installerName = trimmedInstaller
    if (includeAI) payload.dashboardUrl = window.location.href

    createReport.mutate(payload, {
      onSuccess: (res) => { setReportId(res.reportId) },
    })
  }

  function handleReset() {
    setReportId(null)
    setElapsed(0)
    createReport.reset()
  }

  // ── Render helpers ─────────────────────────────────────────────────────────

  function renderIdle() {
    return (
      <div className="space-y-4">
        {/* Optional fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="rg-client-name"
              className="block text-xs font-medium text-gray-600 mb-1"
            >
              Nom du client <span className="text-gray-400">(optionnel)</span>
            </label>
            <input
              id="rg-client-name"
              type="text"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="Ex: Famille Diallo"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-solar-400 focus:border-transparent"
            />
          </div>
          <div>
            <label
              htmlFor="rg-installer-name"
              className="block text-xs font-medium text-gray-600 mb-1"
            >
              Installateur <span className="text-gray-400">(optionnel)</span>
            </label>
            <input
              id="rg-installer-name"
              type="text"
              value={installerName}
              onChange={(e) => setInstallerName(e.target.value)}
              placeholder="Ex: SolarTech Dakar"
              className="w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-solar-400 focus:border-transparent"
            />
          </div>
        </div>

        {/* Include AI checkbox */}
        {hasAIAnalysis && (
          <label className="flex items-center gap-2.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={includeAI}
              onChange={(e) => setIncludeAI(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-solar-500 focus:ring-solar-400 accent-amber-500"
            />
            <span className="text-sm text-gray-700">
              Inclure l'analyse IA dans le rapport
            </span>
          </label>
        )}

        {/* Generate button */}
        <button
          type="button"
          onClick={handleGenerate}
          disabled={createReport.isPending}
          className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-solar-500 hover:bg-solar-600 active:bg-solar-700 disabled:opacity-60 text-white font-semibold py-3 px-6 text-sm transition-colors shadow-sm"
        >
          <FileText size={16} aria-hidden="true" />
          Générer le rapport complet
        </button>
      </div>
    )
  }

  function renderGenerating() {
    return (
      <ReportStatusProgress
        status={status ?? 'pending'}
        elapsedSeconds={elapsed}
      />
    )
  }

  function renderReady() {
    const generatedAt = reportStatus.data?.generatedAt
    return (
      <div className="space-y-4">
        {/* Metadata */}
        {generatedAt !== null && generatedAt !== undefined && (
          <p className="text-xs text-gray-500">
            Généré {formatRelativeTime(generatedAt)}
          </p>
        )}

        {/* Download buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={() =>
              downloadPdf.mutate({
                reportId: reportId ?? '',
                filename: `rapport-solaire-${simulationId.slice(0, 8)}.pdf`,
              })
            }
            disabled={downloadPdf.isPending}
            className="flex items-center justify-center gap-2 rounded-xl bg-solar-500 hover:bg-solar-600 active:bg-solar-700 disabled:opacity-60 text-white font-semibold py-3 px-5 text-sm transition-colors shadow-sm"
          >
            <FileDown size={16} aria-hidden="true" />
            {downloadPdf.isPending ? 'Téléchargement…' : 'Télécharger PDF'}
          </button>
          <button
            type="button"
            onClick={() => downloadHtml.mutate(reportId ?? '')}
            disabled={downloadHtml.isPending}
            className="flex items-center justify-center gap-2 rounded-xl border border-solar-300 bg-solar-50 hover:bg-solar-100 active:bg-solar-200 disabled:opacity-60 text-solar-700 font-semibold py-3 px-5 text-sm transition-colors"
          >
            <ExternalLink size={16} aria-hidden="true" />
            Ouvrir rapport HTML
          </button>
        </div>

        {/* WhatsApp send */}
        <WhatsAppSendButton reportId={reportId ?? ''} />

        {/* Regenerate link */}
        <button
          type="button"
          onClick={handleReset}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
        >
          <RotateCcw size={12} aria-hidden="true" />
          Nouveau rapport
        </button>
      </div>
    )
  }

  function renderFailed() {
    const errMsg =
      createReport.error instanceof Error
        ? createReport.error.message
        : 'La génération du rapport a échoué.'
    return (
      <div className="space-y-3">
        <div
          className="flex items-start gap-2.5 rounded-lg border border-red-200 bg-red-50 px-4 py-3"
          role="alert"
        >
          <AlertTriangle size={16} className="text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
          <p className="text-sm text-red-700">{errMsg}</p>
        </div>
        <button
          type="button"
          onClick={handleReset}
          className="flex items-center gap-2 rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 font-semibold py-2.5 px-4 text-sm transition-colors"
        >
          <RotateCcw size={14} aria-hidden="true" />
          Réessayer
        </button>
      </div>
    )
  }

  // ── Main render ────────────────────────────────────────────────────────────

  return (
    <section
      aria-label="Génération du rapport complet"
      className="rounded-2xl border border-gray-200 bg-white overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100 bg-solar-50">
        <div className="w-8 h-8 rounded-lg bg-white border border-solar-200 flex items-center justify-center">
          <FileText size={16} className="text-solar-600" aria-hidden="true" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Rapport complet</h2>
          <p className="text-[11px] text-gray-500 leading-none mt-0.5">
            PDF 12 pages · HTML interactif · Données Monte Carlo
          </p>
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-4">
        {status === 'ready'
          ? renderReady()
          : status === 'failed' || createReport.isError
            ? renderFailed()
            : isGenerating || createReport.isPending
              ? renderGenerating()
              : renderIdle()}
      </div>
    </section>
  )
}
