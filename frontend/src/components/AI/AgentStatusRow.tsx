// ── AgentStatusRow ────────────────────────────────────────────────────────────
// Shows 3 agent status badges for the multi-agent AI pipeline.

import { Check, X, Cpu } from 'lucide-react'

// ── Types ─────────────────────────────────────────────────────────────────────

type AgentStatus = 'idle' | 'running' | 'done' | 'error'

interface AgentBadgeProps {
  label: string
  model: string
  status: AgentStatus
}

// ── Agent badge ───────────────────────────────────────────────────────────────

function AgentBadge({ label, model, status }: AgentBadgeProps) {
  const statusConfig = {
    idle: {
      dot: <span className="w-2 h-2 rounded-full bg-gray-300 shrink-0" aria-hidden="true" />,
      text: 'En attente',
      textColor: 'text-gray-400',
      border: 'border-gray-200',
      bg: 'bg-white',
    },
    running: {
      dot: (
        <span
          className="w-2 h-2 rounded-full bg-amber-400 shrink-0 animate-pulse"
          aria-hidden="true"
        />
      ),
      text: 'En cours...',
      textColor: 'text-amber-600',
      border: 'border-amber-200',
      bg: 'bg-amber-50',
    },
    done: {
      dot: (
        <Check
          size={14}
          className="text-emerald-500 shrink-0"
          aria-hidden="true"
          strokeWidth={2.5}
        />
      ),
      text: 'Terminé',
      textColor: 'text-emerald-600',
      border: 'border-emerald-200',
      bg: 'bg-emerald-50',
    },
    error: {
      dot: (
        <X
          size={14}
          className="text-red-500 shrink-0"
          aria-hidden="true"
          strokeWidth={2.5}
        />
      ),
      text: 'Erreur',
      textColor: 'text-red-600',
      border: 'border-red-200',
      bg: 'bg-red-50',
    },
  } as const

  const cfg = statusConfig[status]

  return (
    <div
      className={`flex items-center gap-2.5 rounded-xl border px-3.5 py-2.5 flex-1 min-w-0 transition-colors duration-300 ${cfg.bg} ${cfg.border}`}
      role="status"
      aria-label={`Agent ${label} : ${cfg.text}`}
    >
      <Cpu size={14} className="text-gray-400 shrink-0" aria-hidden="true" />
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-xs font-semibold text-gray-700 truncate">{label}</span>
        <span className="text-[10px] text-gray-400 truncate">{model}</span>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        {cfg.dot}
        <span className={`text-[10px] font-medium ${cfg.textColor} hidden sm:block`}>
          {cfg.text}
        </span>
      </div>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

interface AgentStatusRowProps {
  statuses: Record<string, AgentStatus>
}

export default function AgentStatusRow({ statuses }: AgentStatusRowProps) {
  const getStatus = (key: string): AgentStatus =>
    (statuses[key] as AgentStatus | undefined) ?? 'idle'

  return (
    <div className="flex flex-col sm:flex-row gap-2" role="group" aria-label="État des agents IA">
      <AgentBadge
        label="Dimensionnement"
        model="Sonnet 4.6"
        status={getStatus('dimensionnement')}
      />
      <AgentBadge
        label="Rédaction"
        model="Opus 4.6"
        status={getStatus('report_writer')}
      />
      <AgentBadge
        label="Contrôle QA"
        model="Sonnet 4.6"
        status={getStatus('qa')}
      />
    </div>
  )
}
