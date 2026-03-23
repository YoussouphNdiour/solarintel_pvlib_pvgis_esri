// ── WeatherCorrectionBadge ────────────────────────────────────────────────────
// Non-intrusive badge showing real vs simulated irradiance near KPI cards.
// All errors are silently swallowed — this badge must never break the page.

import { useWeatherCorrection } from '@/hooks/useIntegrations'

// ── Props ─────────────────────────────────────────────────────────────────────

interface WeatherCorrectionBadgeProps {
  projectId: string
}

// ── Badge level helpers ───────────────────────────────────────────────────────

type BadgeLevel = 'nominal' | 'mild' | 'heavy'

function getLevel(factor: number): BadgeLevel {
  if (factor >= 0.95) return 'nominal'
  if (factor >= 0.75) return 'mild'
  return 'heavy'
}

const LEVEL_STYLES: Record<BadgeLevel, string> = {
  nominal: 'bg-green-100 text-green-800 border-green-200',
  mild:    'bg-amber-100 text-amber-800 border-amber-200',
  heavy:   'bg-red-100  text-red-800  border-red-200',
}

const LEVEL_ICON: Record<BadgeLevel, string> = {
  nominal: '☀️',
  mild:    '⛅',
  heavy:   '☁️',
}

function labelFor(level: BadgeLevel, factor: number): string {
  const pct = Math.round((1 - factor) * 100)
  switch (level) {
    case 'nominal': return 'Conditions nominales'
    case 'mild':    return `Légère nébulosité (-${pct} %)`
    case 'heavy':   return `Nébulosité importante (-${pct} %)`
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function WeatherCorrectionBadge({
  projectId,
}: WeatherCorrectionBadgeProps) {
  const { data, isLoading, isError } = useWeatherCorrection(projectId)

  // Loading skeleton — matches badge dimensions
  if (isLoading) {
    return (
      <div
        className="inline-block h-6 w-48 animate-pulse rounded-full bg-gray-200"
        aria-label="Chargement des conditions météo"
      />
    )
  }

  // Never render a broken UI — any error is silently hidden
  if (isError || data === undefined) return null

  const level = getLevel(data.correctionFactor)
  const tooltip = `Irradiance mesurée : ${data.measuredDailyKwhM2.toFixed(2)} kWh/m² vs simulée : ${data.simulatedDailyKwhM2.toFixed(2)} kWh/m²`

  return (
    <span
      title={tooltip}
      aria-label={`Correction météo : ${labelFor(level, data.correctionFactor)} — ${tooltip}`}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium cursor-default select-none ${LEVEL_STYLES[level]}`}
    >
      <span aria-hidden="true">{LEVEL_ICON[level]}</span>
      {labelFor(level, data.correctionFactor)}
    </span>
  )
}
