// ── RealtimeProductionChart ───────────────────────────────────────────────────
// Chart.js line chart showing production readings for today (last 24h).

import { useEffect, useMemo, useRef } from 'react'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import type { TooltipItem } from 'chart.js'
import { Line } from 'react-chartjs-2'
import type { MonitoringReading } from '@/types/api'
import ConnectionStatus from './ConnectionStatus'

ChartJS.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

const MAX_POINTS = 96
const FR_TIME = new Intl.DateTimeFormat('fr-SN', { hour: '2-digit', minute: '2-digit' })

interface RealtimeProductionChartProps {
  readings: MonitoringReading[]
  isConnected: boolean
  reconnectAttempts: number
  onReconnect: () => void
}

export default function RealtimeProductionChart({
  readings,
  isConnected,
  reconnectAttempts,
  onReconnect,
}: RealtimeProductionChartProps) {
  const chartRef = useRef<ChartJS<'line'> | null>(null)

  // Most-recent readings first from the hook — reverse for chronological display
  const chronological = useMemo(
    () => [...readings].reverse().slice(-MAX_POINTS),
    [readings],
  )

  const labels = useMemo(
    () => chronological.map((r) => FR_TIME.format(new Date(r.timestamp))),
    [chronological],
  )

  const productionData = useMemo(
    () => chronological.map((r) => {
      // Convert kWh reading to approximate kW power (assume 15-min interval = /0.25)
      return Number((r.productionKwh / 0.25).toFixed(2))
    }),
    [chronological],
  )

  const irradianceData = useMemo(
    () => chronological.map((r) => r.irradianceWm2),
    [chronological],
  )

  const hasIrradiance = irradianceData.some((v) => v !== null)

  // Animate chart when new data arrives
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.update('active')
    }
  }, [readings.length])

  const latestReading = readings[0]
  const lastTime = latestReading
    ? FR_TIME.format(new Date(latestReading.timestamp))
    : null

  if (readings.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-700">Production temps réel — aujourd'hui</h3>
          <ConnectionStatus
            isConnected={isConnected}
            reconnectAttempts={reconnectAttempts}
            onReconnect={onReconnect}
          />
        </div>
        <div className="flex h-[250px] sm:h-[350px] items-center justify-center text-sm text-gray-400">
          En attente de données inverter...
        </div>
      </div>
    )
  }

  const data = {
    labels,
    datasets: [
      {
        label: 'Puissance (kW)',
        data: productionData,
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245,158,11,0.08)',
        borderWidth: 2,
        pointRadius: chronological.length > 20 ? 0 : 3,
        pointHoverRadius: 5,
        tension: 0.35,
        fill: true,
        yAxisID: 'y',
      },
      ...(hasIrradiance
        ? [
            {
              label: 'Irradiance (W/m²)',
              data: irradianceData,
              borderColor: '#d97706',
              backgroundColor: 'transparent',
              borderWidth: 1.5,
              borderDash: [4, 4],
              pointRadius: 0,
              pointHoverRadius: 4,
              tension: 0.35,
              fill: false,
              yAxisID: 'y2',
            },
          ]
        : []),
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400 },
    interaction: { mode: 'index' as const, intersect: false },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: { font: { family: 'Inter, system-ui, sans-serif', size: 11 }, color: '#374151' },
      },
      tooltip: {
        callbacks: {
          label: (ctx: TooltipItem<'line'>) => {
            const val = typeof ctx.parsed.y === 'number' ? ctx.parsed.y : 0
            const unit = ctx.dataset.label?.includes('Irradiance') ? ' W/m²' : ' kW'
            return `${ctx.dataset.label ?? ''}: ${val.toLocaleString('fr-SN')}${unit}`
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          font: { size: 10 },
          color: '#9ca3af',
          maxTicksLimit: 8,
          maxRotation: 0,
        },
      },
      y: {
        position: 'left' as const,
        title: { display: true, text: 'kW', color: '#6b7280', font: { size: 10 } },
        grid: { color: '#f3f4f6' },
        ticks: { font: { size: 10 }, color: '#6b7280' },
      },
      ...(hasIrradiance
        ? {
            y2: {
              position: 'right' as const,
              title: { display: true, text: 'W/m²', color: '#d97706', font: { size: 10 } },
              grid: { drawOnChartArea: false },
              ticks: { font: { size: 10 }, color: '#d97706' },
            },
          }
        : {}),
    },
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-1 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-gray-700">Production temps réel — aujourd'hui</h3>
          {lastTime && (
            <p className="text-xs text-gray-400">Dernière lecture: {lastTime}</p>
          )}
        </div>
        <ConnectionStatus
          isConnected={isConnected}
          reconnectAttempts={reconnectAttempts}
          onReconnect={onReconnect}
        />
      </div>
      <div
        className="h-[250px] sm:h-[350px]"
        role="img"
        aria-label="Graphique de production en temps réel"
      >
        <Line ref={chartRef} data={data} options={options} />
      </div>
    </div>
  )
}
