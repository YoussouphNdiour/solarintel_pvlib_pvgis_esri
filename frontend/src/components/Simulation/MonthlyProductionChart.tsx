import {
  Chart as ChartJS,
  BarController,
  LineController,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'
import type { TooltipItem } from 'chart.js'
import { Chart } from 'react-chartjs-2'
import { MONTHS_FR } from '@/utils/format'
import type { MonthlyData } from '@/types/api'

// ── Register Chart.js components ─────────────────────────────────────────────

ChartJS.register(
  BarController,
  LineController,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
)

// ── Types ─────────────────────────────────────────────────────────────────────

interface MonthlyProductionChartProps {
  monthlyData: MonthlyData[]
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function MonthlyProductionChart({
  monthlyData,
}: MonthlyProductionChartProps) {
  const sorted = [...monthlyData].sort((a, b) => a.month - b.month)

  const labels = sorted.map((d) => MONTHS_FR[d.month - 1] ?? `M${d.month}`)
  const production = sorted.map((d) => d.energyKwh)
  const irradiance = sorted.map((d) => d.irradianceKwhM2)

  const data = {
    labels,
    datasets: [
      {
        type: 'bar' as const,
        label: 'Production (kWh)',
        data: production,
        backgroundColor: '#f59e0b',
        borderColor: '#d97706',
        borderWidth: 1,
        yAxisID: 'y',
        borderRadius: 4,
      },
      {
        type: 'line' as const,
        label: 'Irradiance (kWh/m²)',
        data: irradiance,
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59,130,246,0.15)',
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: '#3b82f6',
        tension: 0.35,
        yAxisID: 'y2',
        fill: false,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          font: { family: 'Inter, system-ui, sans-serif', size: 12 },
          color: '#374151',
        },
      },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'bar' | 'line'>) => {
            const label = ctx.dataset.label ?? ''
            const unit = label.includes('Irradiance') ? ' kWh/m²' : ' kWh'
            const val = typeof ctx.parsed.y === 'number' ? ctx.parsed.y : 0
            return `${label}: ${val.toLocaleString('fr-FR')}${unit}`
          },
        },
      },
      title: {
        display: false,
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          font: { family: 'Inter, system-ui, sans-serif', size: 11 },
          color: '#6b7280',
        },
      },
      y: {
        position: 'left' as const,
        title: {
          display: true,
          text: 'Production (kWh)',
          color: '#6b7280',
          font: { size: 11 },
        },
        grid: { color: '#f3f4f6' },
        ticks: {
          font: { size: 11 },
          color: '#6b7280',
          callback: (v: number | string) =>
            typeof v === 'number' ? v.toLocaleString('fr-FR') : v,
        },
      },
      y2: {
        position: 'right' as const,
        title: {
          display: true,
          text: 'Irradiance (kWh/m²)',
          color: '#6b7280',
          font: { size: 11 },
        },
        grid: { drawOnChartArea: false },
        ticks: {
          font: { size: 11 },
          color: '#6b7280',
        },
      },
    },
  }

  return (
    <div
      className="w-full h-[200px] sm:h-[300px]"
      role="img"
      aria-label="Graphique de production mensuelle solaire et irradiance"
    >
      <Chart type="bar" data={data} options={options} />
    </div>
  )
}
