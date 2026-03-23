// ── EquipmentPriceTable ───────────────────────────────────────────────────────
// Tabbed table of Senegalese market prices for solar panels and inverters.

import { useState } from 'react'
import { useEquipmentPrices } from '@/hooks/useIntegrations'
import { formatFCFA } from '@/utils/format'

// ── Types ─────────────────────────────────────────────────────────────────────

type Tab = 'panels' | 'inverters'

// ── Skeleton row ─────────────────────────────────────────────────────────────

function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr className="border-t border-gray-100">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-3.5 rounded bg-gray-200 animate-pulse" style={{ width: `${60 + (i % 3) * 15}%` }} />
        </td>
      ))}
    </tr>
  )
}

// ── Panel table ───────────────────────────────────────────────────────────────

function PanelTable() {
  const { data, isLoading, isError } = useEquipmentPrices()

  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-red-600" role="alert">
        Erreur lors du chargement des prix. Veuillez réessayer.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm" aria-label="Prix des panneaux solaires">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <th className="px-4 py-3">Modèle</th>
            <th className="px-4 py-3 text-right">Puissance</th>
            <th className="px-4 py-3 text-right">Prix FCFA</th>
            <th className="px-4 py-3 text-right">Prix EUR</th>
            <th className="px-4 py-3">Fournisseur</th>
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} cols={5} />)
            : data?.panels.map((p, i) => (
                <tr
                  key={`${p.model}-${i}`}
                  className="border-t border-gray-100 hover:bg-solar-50/40 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {p.brand} {p.model}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">{p.powerWc} Wc</td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">
                    {formatFCFA(p.priceXof)}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600">
                    {p.priceEur.toLocaleString('fr-FR')} €
                  </td>
                  <td className="px-4 py-3 text-gray-500">{p.supplier}</td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Inverter table ────────────────────────────────────────────────────────────

function InverterTable() {
  const { data, isLoading, isError } = useEquipmentPrices()

  if (isError) {
    return (
      <p className="py-8 text-center text-sm text-red-600" role="alert">
        Erreur lors du chargement des prix. Veuillez réessayer.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[440px] text-sm" aria-label="Prix des onduleurs">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            <th className="px-4 py-3">Modèle</th>
            <th className="px-4 py-3 text-right">Puissance</th>
            <th className="px-4 py-3 text-right">Prix FCFA</th>
            <th className="px-4 py-3">Fournisseur</th>
          </tr>
        </thead>
        <tbody>
          {isLoading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonRow key={i} cols={4} />)
            : data?.inverters.map((inv, i) => (
                <tr
                  key={`${inv.model}-${i}`}
                  className="border-t border-gray-100 hover:bg-solar-50/40 transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-gray-900">
                    {inv.brand} {inv.model}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-700">{inv.kva} kVA</td>
                  <td className="px-4 py-3 text-right font-semibold text-gray-900">
                    {formatFCFA(inv.priceXof)}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{inv.supplier}</td>
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

export default function EquipmentPriceTable() {
  const [activeTab, setActiveTab] = useState<Tab>('panels')

  return (
    <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
      {/* Tab bar */}
      <div className="flex border-b border-gray-200" role="tablist" aria-label="Catégories d'équipements">
        {(['panels', 'inverters'] as const).map((tab) => {
          const label = tab === 'panels' ? 'Panneaux' : 'Onduleurs'
          const isActive = activeTab === tab
          return (
            <button
              key={tab}
              role="tab"
              type="button"
              aria-selected={isActive}
              aria-controls={`tab-panel-${tab}`}
              id={`tab-${tab}`}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 sm:flex-none px-6 py-3 text-sm font-semibold border-b-2 transition-colors ${
                isActive
                  ? 'border-solar-500 text-solar-700'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>

      {/* Table panel */}
      <div
        id={`tab-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`tab-${activeTab}`}
      >
        {activeTab === 'panels' ? <PanelTable /> : <InverterTable />}
      </div>

      {/* Footer note */}
      <div className="border-t border-gray-100 bg-gray-50 px-4 py-2.5">
        <p className="text-xs text-gray-400">
          Prix marché Dakar — actualisés chaque semaine
        </p>
      </div>
    </div>
  )
}
