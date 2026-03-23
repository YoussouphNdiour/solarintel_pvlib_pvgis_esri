// ── MonthlyComparisonChart ────────────────────────────────────────────────────
// Grouped bar chart: actual vs simulated per month with performance line overlay.

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import type { TooltipItem, ScriptableContext } from 'chart.js'
import { Chart } from 'react-chartjs-2'
import { MONTHS_FR } from '@/utils/format'
import type { MonthlyComparison } from '@/types/api'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
)

interface MonthlyComparisonChartProps {
  data: MonthlyComparison[]
}

function perfColor(pct: number): string {
  if (pct >= 90) return 'rgba(34,197,94,0.12)'
  if (pct >= 70) return 'rgba(245,158,11,0.12)'
  return 'rgba(239,68,68,0.12)'
}

export default function MonthlyComparisonChart({ data }: MonthlyComparisonChartProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">
          Comparaison mensuelle — réel vs simulé
        </h3>
        <div className="flex h-[250px] sm:h-[350px] items-center justify-center text-sm text-gray-400">
          Aucune donnée mensuelle disponible
        </div>
      </div>
    )
  }

  const sorted = [...data].sort((a, b) =>
    a.year !== b.year ? a.year - b.year : a.month - b.month,
  )

  const labels = sorted.map((d) => MONTHS_FR[d.month - 1] ?? `M${d.month}`)

  const chartData = {
    labels,
    datasets: [
      {
        type: 'bar' as const,
        label: 'Production simulée (kWh)',
        data: sorted.map((d) => d.simulatedKwh),
        backgroundColor: 'rgba(59,130,246,0.7)',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 4,
        yAxisID: 'y',
      },
      {
        type: 'bar' as const,
        label: 'Production réelle (kWh)',
        data: sorted.map((d) => d.actualKwh),
        backgroundColor: 'rgba(245,158,11,0.8)',
        borderColor: '#d97706',
        borderWidth: 1,
        borderRadius: 4,
        yAxisID: 'y',
      },
      {
        type: 'line' as const,
        label: 'Performance (%)',
        data: sorted.map((d) => d.performancePct),
        borderColor: '#6366f1',
        backgroundColor: (ctx: ScriptableContext<'line'>) => {
          const val = ctx.parsed?.y ?? 0
          return perfColor(val)
        },
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: sorted.map((d) =>
          d.performancePct >= 90 ? '#22c55e' : d.performancePct >= 70 ? '#f59e0b' : '#ef4444',
        ),
        tension: 0.3,
        fill: false,
        yAxisID: 'y2',
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: { font: { family: 'Inter, system-ui, sans-serif', size: 11 }, color: '#374151' },
      },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'bar' | 'line'>) => {
            const val = typeof ctx.parsed.y === 'number' ? ctx.parsed.y : 0
            const unit = ctx.dataset.label?.includes('Performance') ? ' %' : ' kWh'
            return `${ctx.dataset.label ?? ''}: ${val.toLocaleString('fr-SN')}${unit}`
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 11 }, color: '#6b7280' },
      },
      y: {
        position: 'left' as const,
        title: { display: true, text: 'kWh', color: '#6b7280', font: { size: 10 } },
        grid: { color: '#f3f4f6' },
        ticks: {
          font: { size: 10 },
          color: '#6b7280',
          callback: (v: number | string) =>
            typeof v === 'number' ? v.toLocaleString('fr-SN') : v,
        },
      },
      y2: {
        position: 'right' as const,
        min: 0,
        max: 120,
        title: { display: true, text: 'Performance %', color: '#6366f1', font: { size: 10 } },
        grid: { drawOnChartArea: false },
        ticks: {
          font: { size: 10 },
          color: '#6366f1',
          callback: (v: number | string) =>
            typeof v === 'number' ? `${v}%` : v,
        },
      },
    },
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="mb-3 text-sm font-semibold text-gray-700">
        Comparaison mensuelle — réel vs simulé
      </h3>
      <div
        className="h-[250px] sm:h-[350px]"
        role="img"
        aria-label="Graphique comparaison mensuelle production réelle et simulée"
      >
        <Chart type="bar" data={chartData} options={options} />
      </div>
    </div>
  )
}
