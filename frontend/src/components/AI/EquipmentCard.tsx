// ── EquipmentCard ─────────────────────────────────────────────────────────────
// Displays equipment recommendation from the Dimensionnement agent.

import { Zap, Battery, Settings2 } from 'lucide-react'
import type { EquipmentRecommendation } from '@/types/api'

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonLine({ w = 'w-full', h = 'h-3' }: { w?: string; h?: string }) {
  return (
    <div
      className={`${w} ${h} bg-gray-200 rounded animate-pulse`}
      aria-hidden="true"
    />
  )
}

function EquipmentCardSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-4">
      <SkeletonLine w="w-24" h="h-5" />
      <div className="space-y-2">
        <SkeletonLine w="w-full" />
        <SkeletonLine w="w-3/4" />
      </div>
      <div className="space-y-2">
        <SkeletonLine w="w-full" />
        <SkeletonLine w="w-2/3" />
      </div>
      <div className="space-y-1.5">
        <SkeletonLine w="w-full" h="h-2.5" />
        <SkeletonLine w="w-5/6" h="h-2.5" />
        <SkeletonLine w="w-4/6" h="h-2.5" />
      </div>
    </div>
  )
}

// ── System type badge ─────────────────────────────────────────────────────────

const SYSTEM_TYPE_CONFIG = {
  'on-grid': { label: 'On-grid', bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  'hybrid':  { label: 'Hybride',  bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-200' },
  'off-grid':{ label: 'Off-grid', bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
} as const

// ── Component ─────────────────────────────────────────────────────────────────

interface EquipmentCardProps {
  recommendation: EquipmentRecommendation | null
  isLoading: boolean
}

export default function EquipmentCard({
  recommendation,
  isLoading,
}: EquipmentCardProps) {
  if (isLoading || recommendation === null) {
    return <EquipmentCardSkeleton />
  }

  const sysConfig = SYSTEM_TYPE_CONFIG[recommendation.systemType]

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-4 h-full">
      {/* Header: title + system type badge */}
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-800">Équipements recommandés</h3>
        <span
          className={`shrink-0 text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${sysConfig.bg} ${sysConfig.text} ${sysConfig.border}`}
        >
          {sysConfig.label}
        </span>
      </div>

      {/* Inverter */}
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-solar-50 border border-solar-200 flex items-center justify-center shrink-0">
          <Zap size={15} className="text-solar-600" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-0.5">
            Onduleur
          </p>
          <p className="text-sm font-semibold text-gray-900 leading-snug">
            {recommendation.inverterBrand} {recommendation.inverterModel}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            {recommendation.inverterKva} kVA
          </p>
        </div>
      </div>

      {/* Battery */}
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center shrink-0">
          <Battery size={15} className="text-gray-500" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide mb-0.5">
            Batterie
          </p>
          {recommendation.batteryModel !== null && recommendation.batteryKwh !== null ? (
            <>
              <p className="text-sm font-semibold text-gray-900 leading-snug">
                {recommendation.batteryModel}
              </p>
              <p className="text-xs text-gray-500 mt-0.5">
                {recommendation.batteryKwh} kWh
              </p>
            </>
          ) : (
            <p className="text-sm text-gray-400 italic">Aucune batterie (on-grid)</p>
          )}
        </div>
      </div>

      {/* Reasoning */}
      <div className="border-t border-gray-100 pt-3 flex items-start gap-2">
        <Settings2 size={13} className="text-gray-400 shrink-0 mt-0.5" aria-hidden="true" />
        <p className="text-xs text-gray-500 italic leading-relaxed">
          {recommendation.reasoning}
        </p>
      </div>
    </div>
  )
}
