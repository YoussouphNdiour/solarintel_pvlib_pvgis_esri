// ── LatestReadingsTable ───────────────────────────────────────────────────────
// Table of last 20 monitoring readings, updates live via WebSocket.

import type { MonitoringReading } from '@/types/api'

interface LatestReadingsTableProps {
  readings: MonitoringReading[]
}

const FR_TIME = new Intl.DateTimeFormat('fr-SN', {
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
})

// Source icons (antenna = webhook, cloud = open_meteo)
function SourceIcon({ source }: { source: string }) {
  if (source === 'webhook') {
    return (
      <span title="Inverter webhook" aria-label="Source: inverter webhook">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="inline text-solar-600"
          aria-hidden="true"
        >
          <path d="M5 12.55a11 11 0 0 1 14.08 0" />
          <path d="M1.42 9a16 16 0 0 1 21.16 0" />
          <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
          <circle cx="12" cy="20" r="1" />
        </svg>
      </span>
    )
  }
  if (source === 'open_meteo') {
    return (
      <span title="Open-Meteo (météo)" aria-label="Source: Open-Meteo">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="inline text-blue-500"
          aria-hidden="true"
        >
          <path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9z" />
        </svg>
      </span>
    )
  }
  return <span className="text-gray-400 text-xs">{source}</span>
}

const MAX_ROWS = 20

export default function LatestReadingsTable({ readings }: LatestReadingsTableProps) {
  const displayed = readings.slice(0, MAX_ROWS)

  if (displayed.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">Dernières lectures</h3>
        <p className="py-6 text-center text-sm text-gray-400">
          En attente de lectures inverter...
        </p>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="border-b border-gray-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-gray-700">
          Dernières lectures
          <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-xs font-normal text-gray-500">
            {displayed.length}
          </span>
        </h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" aria-label="Dernières lectures de production">
          <thead>
            <tr className="sticky top-0 bg-gray-50 text-left">
              <th className="px-3 py-2 font-semibold text-gray-500">Heure</th>
              <th className="px-3 py-2 font-semibold text-gray-500">Prod. kWh</th>
              <th className="px-3 py-2 font-semibold text-gray-500">Puissance kW</th>
              <th className="px-3 py-2 font-semibold text-gray-500">Irrad. W/m²</th>
              <th className="px-3 py-2 font-semibold text-gray-500">Source</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map((r, idx) => (
              <tr
                key={r.id}
                className={`border-t border-gray-50 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
              >
                <td className="px-3 py-2 font-mono text-gray-700 tabular-nums">
                  {FR_TIME.format(new Date(r.timestamp))}
                </td>
                <td className="px-3 py-2 tabular-nums text-gray-700">
                  {r.productionKwh.toLocaleString('fr-SN', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
                </td>
                <td className="px-3 py-2 tabular-nums text-gray-700">
                  {(r.productionKwh / 0.25).toLocaleString('fr-SN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </td>
                <td className="px-3 py-2 tabular-nums text-gray-500">
                  {r.irradianceWm2 !== null
                    ? r.irradianceWm2.toLocaleString('fr-SN', { maximumFractionDigits: 1 })
                    : '—'}
                </td>
                <td className="px-3 py-2">
                  <SourceIcon source={r.source} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
