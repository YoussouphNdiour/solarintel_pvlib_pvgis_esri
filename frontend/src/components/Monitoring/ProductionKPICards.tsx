// ── ProductionKPICards ────────────────────────────────────────────────────────
// Three KPI cards: Aujourd'hui / Ce mois / Cette année with performance colors.

import type { ProductionStats } from '@/types/api'

interface ProductionKPICardsProps {
  stats: ProductionStats
}

// ── Performance badge ─────────────────────────────────────────────────────────

function PerformanceBadge({ pct }: { pct: number }) {
  if (pct >= 90) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
        <span aria-hidden="true">✓</span> {pct.toFixed(1)} %
      </span>
    )
  }
  if (pct >= 70) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
        <span aria-hidden="true">⚠</span> {pct.toFixed(1)} %
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
      <span aria-hidden="true">✗</span> {pct.toFixed(1)} %
    </span>
  )
}

// ── Individual KPI card ───────────────────────────────────────────────────────

interface KPICardProps {
  title: string
  actualKwh: number
  expectedKwh: number
  performancePct: number
}

function KPICard({ title, actualKwh, expectedKwh, performancePct }: KPICardProps) {
  const formatted = actualKwh.toLocaleString('fr-SN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: actualKwh < 10 ? 1 : 0,
  })

  const expectedFormatted = expectedKwh.toLocaleString('fr-SN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {title}
      </p>

      <p
        className="mt-2 text-3xl font-bold tabular-nums text-gray-900 transition-all duration-500"
        aria-live="polite"
      >
        {formatted}
        <span className="ml-1 text-sm font-normal text-gray-500">kWh</span>
      </p>

      <div className="mt-2 flex items-center justify-between">
        <p className="text-xs text-gray-400">
          Prévu: {expectedFormatted} kWh
        </p>
        <PerformanceBadge pct={performancePct} />
      </div>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ProductionKPICards({ stats }: ProductionKPICardsProps) {
  return (
    <div
      className="grid grid-cols-1 gap-4 sm:grid-cols-3"
      role="region"
      aria-label="Indicateurs clés de production"
    >
      <KPICard
        title="Aujourd'hui"
        actualKwh={stats.todayKwh}
        expectedKwh={stats.todayExpectedKwh}
        performancePct={stats.todayPerformancePct}
      />
      <KPICard
        title="Ce mois"
        actualKwh={stats.monthKwh}
        expectedKwh={stats.monthExpectedKwh}
        performancePct={stats.monthPerformancePct}
      />
      <KPICard
        title="Cette année"
        actualKwh={stats.yearKwh}
        expectedKwh={stats.yearExpectedKwh}
        performancePct={stats.yearPerformancePct}
      />
    </div>
  )
}
