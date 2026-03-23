// ── AIAnalysisPanel ───────────────────────────────────────────────────────────
// Main panel that orchestrates the AI multi-agent analysis display.

import { useEffect } from 'react'
import { Bot, AlertTriangle, RotateCcw, Sparkles } from 'lucide-react'
import { useAIAnalysis } from '@/hooks/useAIAnalysis'
import AgentStatusRow from './AgentStatusRow'
import EquipmentCard from './EquipmentCard'
import QAMatrix from './QAMatrix'
import NarrativePanel from './NarrativePanel'

// ── Types ─────────────────────────────────────────────────────────────────────

interface AIAnalysisPanelProps {
  simulationId: string
  onAnalysisComplete?: () => void
}

// ── Error Banner ──────────────────────────────────────────────────────────────

interface ErrorBannerProps {
  errors: string[]
  onRetry: () => void
}

function ErrorBanner({ errors, onRetry }: ErrorBannerProps) {
  return (
    <div
      className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-3"
      role="alert"
    >
      <AlertTriangle size={16} className="text-red-500 shrink-0" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-red-800">
          Analyse IA indisponible — vérifiez votre connexion
        </p>
        {errors.length > 0 && (
          <p className="text-xs text-red-600 mt-0.5 truncate" title={errors.join(' | ')}>
            {errors[errors.length - 1]}
          </p>
        )}
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="flex items-center gap-1.5 text-xs font-semibold text-red-700 hover:text-red-900 border border-red-300 rounded-lg px-3 py-1.5 hover:bg-red-100 transition-colors shrink-0"
      >
        <RotateCcw size={12} aria-hidden="true" />
        Réessayer
      </button>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AIAnalysisPanel({
  simulationId,
  onAnalysisComplete,
}: AIAnalysisPanelProps) {
  const {
    isRunning,
    agentStatuses,
    narrative,
    equipmentRec,
    qaResults,
    finalResult,
    errors,
    startAnalysis,
    reset,
  } = useAIAnalysis()

  // Notify parent once analysis completes successfully.
  useEffect(() => {
    if (finalResult !== null && onAnalysisComplete !== undefined) {
      onAnalysisComplete()
    }
  }, [finalResult, onAnalysisComplete])

  // Cleanup on unmount
  useEffect(() => {
    return () => { reset() }
  }, [reset])

  const hasStarted =
    isRunning ||
    finalResult !== null ||
    errors.length > 0 ||
    narrative.trim() !== '' ||
    equipmentRec !== null

  const hasFatalError =
    !isRunning && errors.length > 0 && finalResult === null && equipmentRec === null

  // Derive per-section loading states from agent statuses
  const equipmentLoading =
    agentStatuses['dimensionnement'] === 'idle' ||
    agentStatuses['dimensionnement'] === 'running'
  const qaLoading =
    agentStatuses['qa'] === 'idle' || agentStatuses['qa'] === 'running'
  const narrativeStreaming = agentStatuses['report_writer'] === 'running'
  const narrativeLoading =
    agentStatuses['report_writer'] === 'idle' && narrative.trim() === ''

  function handleStart() {
    startAnalysis(simulationId)
  }

  function handleRetry() {
    reset()
    startAnalysis(simulationId)
  }

  return (
    <section
      aria-label="Analyse IA multi-agent"
      className="rounded-2xl border border-gray-200 bg-gray-50 overflow-hidden"
    >
      {/* Panel header */}
      <div className="flex items-center justify-between gap-3 px-5 py-4 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-solar-50 border border-solar-200 flex items-center justify-center">
            <Bot size={16} className="text-solar-600" aria-hidden="true" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-900">Analyse IA Multi-Agent</h2>
            <p className="text-[11px] text-gray-400 leading-none mt-0.5">
              LangGraph · Dimensionnement · Rédaction · QA
            </p>
          </div>
        </div>

        {/* Launch button when not yet started */}
        {!hasStarted && (
          <button
            type="button"
            onClick={handleStart}
            className="flex items-center gap-2 bg-solar-500 hover:bg-solar-600 active:bg-solar-700 text-white font-semibold text-sm px-4 py-2 rounded-xl transition-colors shadow-sm"
          >
            <Sparkles size={14} aria-hidden="true" />
            Lancer l'analyse IA
          </button>
        )}

        {/* Running indicator */}
        {isRunning && (
          <div className="flex items-center gap-2 text-xs text-amber-600 font-medium">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" aria-hidden="true" />
            Analyse en cours…
          </div>
        )}

        {/* Reset button when complete */}
        {!isRunning && finalResult !== null && (
          <button
            type="button"
            onClick={reset}
            className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg px-2.5 py-1.5 hover:bg-gray-50 transition-colors"
            aria-label="Réinitialiser l'analyse IA"
          >
            <RotateCcw size={12} aria-hidden="true" />
            Réinitialiser
          </button>
        )}
      </div>

      {/* Body */}
      {hasStarted && (
        <div className="p-4 sm:p-5 space-y-4">
          {/* Agent status row */}
          <AgentStatusRow statuses={agentStatuses} />

          {/* Fatal error banner */}
          {hasFatalError && (
            <ErrorBanner errors={errors} onRetry={handleRetry} />
          )}

          {/* Equipment + QA side by side (stack on mobile) */}
          {(isRunning || equipmentRec !== null || qaResults !== null) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <EquipmentCard
                recommendation={equipmentRec}
                isLoading={isRunning && equipmentLoading}
              />
              <QAMatrix
                qaResults={qaResults}
                isLoading={isRunning && qaLoading}
              />
            </div>
          )}

          {/* Narrative — full width */}
          {(isRunning || narrative.trim() !== '') && (
            <NarrativePanel
              narrative={narrative}
              isStreaming={narrativeStreaming}
              isLoading={narrativeLoading && isRunning}
            />
          )}

          {/* Non-fatal partial errors */}
          {errors.length > 0 && finalResult !== null && (
            <div
              className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-xs text-amber-700"
              role="alert"
            >
              <span className="font-semibold">Avertissements : </span>
              {errors.join(' — ')}
            </div>
          )}
        </div>
      )}
    </section>
  )
}
