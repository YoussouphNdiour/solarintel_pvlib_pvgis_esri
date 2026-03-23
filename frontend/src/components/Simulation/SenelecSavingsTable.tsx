import { formatFCFA, formatKwh, MONTHS_FR } from '@/utils/format'
import type { SenelecMonthlySavings } from '@/types/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SenelecSavingsTableProps {
  breakdown: SenelecMonthlySavings[]
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SenelecSavingsTable({
  breakdown,
}: SenelecSavingsTableProps) {
  const sorted = [...breakdown].sort((a, b) => a.month - b.month)

  const totals = sorted.reduce(
    (acc, row) => ({
      productionKwh: acc.productionKwh + row.productionKwh,
      consumptionKwh: acc.consumptionKwh + row.consumptionKwh,
      beforeXof: acc.beforeXof + row.beforeXof,
      afterXof: acc.afterXof + row.afterXof,
      savingsXof: acc.savingsXof + row.savingsXof,
    }),
    { productionKwh: 0, consumptionKwh: 0, beforeXof: 0, afterXof: 0, savingsXof: 0 },
  )

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table
        className="min-w-full text-sm"
        aria-label="Tableau des économies mensuelles SENELEC"
      >
        <thead>
          <tr className="bg-gray-50 border-b border-gray-200">
            <th
              scope="col"
              className="px-4 py-3 text-left font-semibold text-gray-700 whitespace-nowrap"
            >
              Mois
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right font-semibold text-gray-700 whitespace-nowrap"
            >
              Production (kWh)
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right font-semibold text-gray-700 whitespace-nowrap"
            >
              Consommation (kWh)
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right font-semibold text-gray-700 whitespace-nowrap"
            >
              Facture avant
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right font-semibold text-gray-700 whitespace-nowrap"
            >
              Facture après
            </th>
            <th
              scope="col"
              className="px-4 py-3 text-right font-semibold text-gray-700 whitespace-nowrap"
            >
              Économies
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={row.month}
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
            >
              <td className="px-4 py-2.5 text-gray-700 font-medium">
                {MONTHS_FR[row.month - 1] ?? `M${row.month}`}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-600">
                {formatKwh(row.productionKwh)}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-600">
                {formatKwh(row.consumptionKwh)}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-600">
                {formatFCFA(row.beforeXof)}
              </td>
              <td className="px-4 py-2.5 text-right text-gray-600">
                {formatFCFA(row.afterXof)}
              </td>
              <td
                className={`px-4 py-2.5 text-right font-medium ${
                  row.savingsXof > 0 ? 'text-green-600' : 'text-gray-600'
                }`}
              >
                {formatFCFA(row.savingsXof)}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="bg-gray-50 border-t-2 border-gray-300">
            <td className="px-4 py-3 font-bold text-gray-900">Total</td>
            <td className="px-4 py-3 text-right font-bold text-gray-900">
              {formatKwh(totals.productionKwh)}
            </td>
            <td className="px-4 py-3 text-right font-bold text-gray-900">
              {formatKwh(totals.consumptionKwh)}
            </td>
            <td className="px-4 py-3 text-right font-bold text-gray-900">
              {formatFCFA(totals.beforeXof)}
            </td>
            <td className="px-4 py-3 text-right font-bold text-gray-900">
              {formatFCFA(totals.afterXof)}
            </td>
            <td className="px-4 py-3 text-right font-bold text-green-700">
              {formatFCFA(totals.savingsXof)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}
