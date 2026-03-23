import { useState } from 'react'
import { RotateCcw, Sparkles } from 'lucide-react'
import { formatFCFA, formatKwh, formatKwc } from '@/utils/format'
import MonthlyProductionChart from './MonthlyProductionChart'
import SenelecSavingsTable from './SenelecSavingsTable'
import AIAnalysisPanel from '@/components/AI/AIAnalysisPanel'
import ReportGeneratorCard from '@/components/Report/ReportGeneratorCard'
import WeatherCorrectionBadge from '@/components/Integration/WeatherCorrectionBadge'
import type { SimulationFull } from '@/types/api'

// ── Types ─────────────────────────────────────────────────────────────────────

interface SimulationResultsProps {
  simulation: SimulationFull
  onNewSimulation: () => void
}

// ── Sub-component: KPI Card ───────────────────────────────────────────────────

interface KpiCardProps {
  label: string
  value: string
  accent?: boolean
}

function KpiCard({ label, value, accent = false }: KpiCardProps) {
  return (
    <div
      className={`rounded-xl border p-4 flex flex-col gap-1 ${
        accent
          ? 'bg-solar-50 border-solar-200'
          : 'bg-white border-gray-200'
      }`}
    >
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
        {label}
      </span>
      <span className={`text-xl font-bold ${accent ? 'text-solar-700' : 'text-gray-900'}`}>
        {value}
      </span>
    </div>
  )
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function SimulationResults({
  simulation,
  onNewSimulation,
}: SimulationResultsProps) {
  const [showAIPanel, setShowAIPanel] = useState(false)
  const [aiAnalysisDone, setAiAnalysisDone] = useState(false)

  const annualSavings = simulation.senelecSavingsXof ?? 0
  const installCost = simulation.installationCostXof
  const payback = simulation.paybackYears
  const roi25 = simulation.roiPercent

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <section aria-label="Indicateurs clés de performance">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-base font-semibold text-gray-700">Résultats</h2>
          <WeatherCorrectionBadge projectId={simulation.projectId} />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            label="Puissance crête"
            value={formatKwc(simulation.peakKwc)}
            accent
          />
          <KpiCard
            label="Production annuelle"
            value={formatKwh(simulation.annualKwh)}
          />
          <KpiCard
            label="Productivité spécifique"
            value={`${Math.round(simulation.specificYield).toLocaleString('fr-FR')} kWh/kWp`}
          />
          <KpiCard
            label="Performance ratio"
            value={`${(simulation.performanceRatio * 100).toFixed(1)} %`}
          />
        </div>
      </section>

      {/* Monthly chart */}
      <section aria-label="Production mensuelle">
        <h2 className="text-base font-semibold text-gray-700 mb-3">
          Production mensuelle
        </h2>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <MonthlyProductionChart monthlyData={simulation.monthlyData} />
        </div>
      </section>

      {/* SENELEC savings table */}
      {simulation.monthlyBreakdown.length > 0 && (
        <section aria-label="Économies SENELEC mensuelles">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            Économies SENELEC mois par mois
          </h2>
          <SenelecSavingsTable breakdown={simulation.monthlyBreakdown} />
        </section>
      )}

      {/* ROI summary card */}
      <section aria-label="Analyse financière et retour sur investissement">
        <h2 className="text-base font-semibold text-gray-700 mb-3">
          Analyse financière
        </h2>
        <div className="bg-white rounded-xl border border-gray-200 p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Coût installation
            </span>
            <span className="text-lg font-bold text-gray-900">
              {formatFCFA(installCost)}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Économies annuelles
            </span>
            <span className="text-lg font-bold text-green-700">
              {formatFCFA(annualSavings)}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              Retour sur invest.
            </span>
            <span className="text-lg font-bold text-gray-900">
              {payback !== null ? `${payback.toFixed(1)} ans` : '—'}
            </span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-gray-500 font-medium uppercase tracking-wide">
              ROI 25 ans
            </span>
            <span className="text-lg font-bold text-solar-700">
              {roi25 !== null ? `${roi25.toFixed(0)} %` : '—'}
            </span>
          </div>
        </div>
      </section>

      {/* Action buttons */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          type="button"
          onClick={() => setShowAIPanel((v) => !v)}
          className={`flex items-center justify-center gap-2 rounded-xl border font-semibold py-3 px-5 text-sm transition-colors ${
            showAIPanel
              ? 'bg-solar-500 border-solar-500 text-white hover:bg-solar-600'
              : 'border-solar-400 bg-solar-50 hover:bg-solar-100 text-solar-700'
          }`}
          aria-expanded={showAIPanel}
          aria-controls="ai-analysis-panel"
        >
          <Sparkles size={16} aria-hidden="true" />
          {showAIPanel ? "Masquer l'analyse IA" : "Analyser avec l'IA"}
        </button>
        <button
          type="button"
          onClick={onNewSimulation}
          className="flex items-center justify-center gap-2 rounded-xl border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 font-semibold py-3 px-5 text-sm transition-colors"
        >
          <RotateCcw size={16} aria-hidden="true" />
          Nouvelle simulation
        </button>
      </div>

      {/* AI Analysis Panel — inline expansion below results */}
      {showAIPanel && (
        <div id="ai-analysis-panel">
          <AIAnalysisPanel
            simulationId={simulation.id}
            onAnalysisComplete={() => setAiAnalysisDone(true)}
          />
        </div>
      )}

      {/* Report Generator — always shown after simulation */}
      <ReportGeneratorCard
        simulationId={simulation.id}
        hasAIAnalysis={aiAnalysisDone}
      />
    </div>
  )
}
