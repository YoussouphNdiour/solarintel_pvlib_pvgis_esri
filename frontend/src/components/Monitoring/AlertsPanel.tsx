// ── AlertsPanel ───────────────────────────────────────────────────────────────
// List of recent performance alerts with severity coding and slide-in animation.

import { formatRelativeTime } from '@/utils/format'

interface Alert {
  message: string
  receivedAt: string
}

interface AlertsPanelProps {
  alerts: Alert[]
}

function parseSeverity(message: string): 'critical' | 'warning' | 'info' {
  // Parse performance percentage from alert message if present
  const match = message.match(/(\d+(?:\.\d+)?)\s*%/)
  if (match?.[1] !== undefined) {
    const pct = parseFloat(match[1])
    if (pct < 60) return 'critical'
    if (pct < 80) return 'warning'
  }
  return 'info'
}

function SeverityBadge({ severity }: { severity: 'critical' | 'warning' | 'info' }) {
  const styles = {
    critical: 'bg-red-100 text-red-700',
    warning: 'bg-amber-100 text-amber-700',
    info: 'bg-blue-100 text-blue-700',
  }
  const labels = {
    critical: 'Critique',
    warning: 'Avertissement',
    info: 'Info',
  }
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${styles[severity]}`}>
      {labels[severity]}
    </span>
  )
}

const MAX_DISPLAYED = 10

export default function AlertsPanel({ alerts }: AlertsPanelProps) {
  const displayed = alerts.slice(0, MAX_DISPLAYED)

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">Alertes</h3>
        {alerts.length > MAX_DISPLAYED && (
          <span className="text-xs text-gray-400">
            +{alerts.length - MAX_DISPLAYED} masquées
          </span>
        )}
      </div>

      {displayed.length === 0 ? (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 px-3 py-4 text-sm text-green-700">
          <span aria-hidden="true" className="text-base">✓</span>
          <span>Aucune alerte — performance nominale</span>
        </div>
      ) : (
        <ul className="space-y-2" role="list" aria-label="Liste des alertes de performance">
          {displayed.map((alert, idx) => {
            const severity = parseSeverity(alert.message)
            const borderColor = {
              critical: 'border-red-200',
              warning: 'border-amber-200',
              info: 'border-blue-200',
            }[severity]

            return (
              <li
                key={`${alert.receivedAt}-${idx}`}
                className={`animate-slide-down rounded-lg border ${borderColor} bg-white px-3 py-2.5`}
                style={{ animationDelay: `${idx * 40}ms` }}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="flex-1 text-xs leading-relaxed text-gray-700">
                    {alert.message}
                  </p>
                  <SeverityBadge severity={severity} />
                </div>
                <p className="mt-1 text-xs text-gray-400">
                  {formatRelativeTime(alert.receivedAt)}
                </p>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
