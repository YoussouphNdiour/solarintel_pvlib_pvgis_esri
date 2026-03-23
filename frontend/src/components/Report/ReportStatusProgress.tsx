// ── ReportStatusProgress ──────────────────────────────────────────────────────
// Animated 4-step progress indicator for async report generation.

import { CheckCircle2, Circle, Database, BarChart3, FileText, Globe } from 'lucide-react'
import type { ReportStatus } from '@/types/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Step {
  id: number
  label: string
  sublabel: string
  Icon: React.ElementType
}

interface ReportStatusProgressProps {
  status: ReportStatus
  /** Elapsed seconds since generation started — used to estimate time remaining */
  elapsedSeconds?: number
}

// ── Step definitions ──────────────────────────────────────────────────────────

const STEPS: Step[] = [
  { id: 0, label: 'Chargement des données',      sublabel: 'simulation + économies',     Icon: Database  },
  { id: 1, label: 'Calcul Monte Carlo',           sublabel: 'N=1000 itérations',           Icon: BarChart3  },
  { id: 2, label: 'Génération PDF',               sublabel: '12 pages, graphiques',        Icon: FileText   },
  { id: 3, label: 'Export HTML interactif',       sublabel: 'dashboard téléchargeable',    Icon: Globe      },
]

// Estimated total duration in seconds used to derive time remaining display.
const ESTIMATED_TOTAL_SECONDS = 20

// ── Step state helpers ────────────────────────────────────────────────────────

function getActiveStepIndex(status: ReportStatus): number {
  if (status === 'pending')    return 0
  if (status === 'generating') return 1
  if (status === 'ready')      return STEPS.length // all done
  return 1 // failed — keep at step 1
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ReportStatusProgress({
  status,
  elapsedSeconds = 0,
}: ReportStatusProgressProps) {
  const activeStep = getActiveStepIndex(status)

  const remaining = Math.max(
    0,
    ESTIMATED_TOTAL_SECONDS - elapsedSeconds,
  )
  const remainingLabel =
    status === 'ready'
      ? 'Terminé'
      : remaining <= 2
        ? 'Finalisation…'
        : `~${remaining} seconde${remaining > 1 ? 's' : ''} restante${remaining > 1 ? 's' : ''}`

  return (
    <div className="space-y-3" role="status" aria-label="Progression de la génération du rapport">
      {/* Steps */}
      <ol className="space-y-2">
        {STEPS.map((step) => {
          const isDone    = activeStep > step.id
          const isCurrent = activeStep === step.id
          const isPending = activeStep < step.id

          return (
            <li
              key={step.id}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 transition-colors ${
                isCurrent ? 'bg-solar-50 border border-solar-200' : 'bg-transparent'
              }`}
            >
              {/* Step indicator */}
              {isDone && (
                <CheckCircle2
                  size={18}
                  className="text-green-500 shrink-0"
                  aria-hidden="true"
                />
              )}
              {isCurrent && (
                <span
                  className="w-[18px] h-[18px] rounded-full bg-solar-400 animate-pulse shrink-0 flex-none"
                  aria-hidden="true"
                />
              )}
              {isPending && (
                <Circle
                  size={18}
                  className="text-gray-300 shrink-0"
                  aria-hidden="true"
                />
              )}

              {/* Icon + labels */}
              <step.Icon
                size={14}
                className={`shrink-0 ${
                  isDone
                    ? 'text-green-500'
                    : isCurrent
                      ? 'text-solar-600'
                      : 'text-gray-300'
                }`}
                aria-hidden="true"
              />
              <div className="min-w-0 flex-1">
                <p
                  className={`text-sm font-medium leading-tight ${
                    isDone
                      ? 'text-green-700'
                      : isCurrent
                        ? 'text-solar-800'
                        : 'text-gray-400'
                  }`}
                >
                  {step.label}
                  {isCurrent && (
                    <span className="ml-1 text-solar-500">…</span>
                  )}
                </p>
                <p
                  className={`text-[11px] leading-tight mt-0.5 ${
                    isDone ? 'text-green-500' : isCurrent ? 'text-solar-500' : 'text-gray-300'
                  }`}
                >
                  {step.sublabel}
                </p>
              </div>
            </li>
          )
        })}
      </ol>

      {/* Time remaining */}
      <p className="text-xs text-gray-500 text-center" aria-live="polite">
        {remainingLabel}
      </p>
    </div>
  )
}
