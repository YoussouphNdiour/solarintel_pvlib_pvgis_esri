// ── QAMatrix ──────────────────────────────────────────────────────────────────
// 8-criteria QA validation table with staggered row animation.

import { Check, X, Minus } from 'lucide-react'
import type { AnalysisResult, QACriterion } from '@/types/api'

// ── Skeleton ──────────────────────────────────────────────────────────────────

function QAMatrixSkeleton() {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="h-5 w-28 bg-gray-200 rounded animate-pulse" aria-hidden="true" />
        <div className="h-5 w-16 bg-gray-200 rounded-full animate-pulse" aria-hidden="true" />
      </div>
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex gap-2 items-center" aria-hidden="true">
            <div className="h-3 w-6 bg-gray-200 rounded animate-pulse" />
            <div className="h-3 flex-1 bg-gray-200 rounded animate-pulse" />
            <div className="h-3 w-12 bg-gray-200 rounded animate-pulse" />
            <div className="h-3 w-12 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 w-4 bg-gray-200 rounded-full animate-pulse" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Status icon ───────────────────────────────────────────────────────────────

function StatusIcon({ status }: { status: QACriterion['status'] }) {
  if (status === 'PASS') {
    return (
      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-emerald-100">
        <Check size={11} className="text-emerald-600" strokeWidth={2.5} aria-hidden="true" />
      </span>
    )
  }
  if (status === 'FAIL') {
    return (
      <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-red-100">
        <X size={11} className="text-red-600" strokeWidth={2.5} aria-hidden="true" />
      </span>
    )
  }
  return (
    <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-gray-100">
      <Minus size={11} className="text-gray-400" strokeWidth={2.5} aria-hidden="true" />
    </span>
  )
}

// ── Criterion row ─────────────────────────────────────────────────────────────

interface CriterionRowProps {
  criterion: QACriterion
  index: number
}

function CriterionRow({ criterion, index }: CriterionRowProps) {
  return (
    <tr
      className="border-t border-gray-100 animate-[fadeSlideIn_0.3s_ease_both]"
      style={{ animationDelay: `${index * 60}ms` }}
      title={criterion.comment}
    >
      <td className="py-2 pr-2 text-xs font-mono font-bold text-gray-400 whitespace-nowrap">
        {criterion.code}
      </td>
      <td className="py-2 pr-3 text-xs text-gray-700 leading-snug">
        {criterion.label}
      </td>
      <td className="py-2 pr-2 text-xs font-medium text-gray-800 whitespace-nowrap">
        {criterion.value ?? '—'}
      </td>
      <td className="py-2 pr-3 text-xs text-gray-400 whitespace-nowrap">
        ≤ {criterion.threshold}
      </td>
      <td className="py-2">
        <span className="sr-only">{criterion.status}</span>
        <StatusIcon status={criterion.status} />
      </td>
    </tr>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

interface QAMatrixProps {
  qaResults: AnalysisResult['qaResults'] | null
  isLoading: boolean
}

export default function QAMatrix({ qaResults, isLoading }: QAMatrixProps) {
  if (isLoading || qaResults === null) {
    return <QAMatrixSkeleton />
  }

  const overallPassed = qaResults.overall === 'PASS'

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 h-full">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-gray-800">Contrôle QA</h3>
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full font-medium">
            {qaResults.score}/8 critères
          </span>
        </div>
        <span
          className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
            overallPassed
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-red-50 text-red-700 border-red-200'
          }`}
          role="status"
          aria-label={`Résultat global QA : ${qaResults.overall}`}
        >
          {overallPassed ? 'PASS' : 'FAIL'}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto -mx-1 px-1">
        <table className="w-full min-w-[340px]">
          <thead>
            <tr>
              <th className="text-left text-[10px] text-gray-400 font-medium pb-1.5 pr-2">Code</th>
              <th className="text-left text-[10px] text-gray-400 font-medium pb-1.5 pr-3">Critère</th>
              <th className="text-left text-[10px] text-gray-400 font-medium pb-1.5 pr-2">Valeur</th>
              <th className="text-left text-[10px] text-gray-400 font-medium pb-1.5 pr-3">Seuil</th>
              <th className="text-left text-[10px] text-gray-400 font-medium pb-1.5">OK</th>
            </tr>
          </thead>
          <tbody>
            {qaResults.criteria.map((criterion, i) => (
              <CriterionRow key={criterion.code} criterion={criterion} index={i} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
