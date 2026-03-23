import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { MapPin, Settings, BarChart2, CheckCircle } from 'lucide-react'
import ArcGISMap from '@/components/Map/ArcGISMap'
import SimulationForm from '@/components/Simulation/SimulationForm'
import SimulationResults from '@/components/Simulation/SimulationResults'
import { useSimulationStore } from '@/stores/simulationStore'
import { useProjectStore } from '@/stores/projectStore'
import { useCreateSimulation } from '@/hooks/useSimulations'
import type { SimulationFull, SimulationRequest } from '@/types/api'

// ── Polygon area helper (Shoelace, approximate metres²) ───────────────────────

function polygonAreaM2(ring: number[][]): number {
  let area = 0
  const n = ring.length
  for (let i = 0; i < n; i++) {
    const [x1, y1] = ring[i]!
    const [x2, y2] = ring[(i + 1) % n]!
    const mLng = 111_320 * Math.cos(((y1 ?? 0) * Math.PI) / 180)
    area += (x1 ?? 0) * mLng * (y2 ?? 0) * 110_540
    area -= (x2 ?? 0) * mLng * (y1 ?? 0) * 110_540
  }
  return Math.abs(area) / 2
}

type Step = 1 | 2 | 3

const STEPS = [
  { id: 1 as Step, label: 'Zone', Icon: MapPin },
  { id: 2 as Step, label: 'Paramètres', Icon: Settings },
  { id: 3 as Step, label: 'Résultats', Icon: BarChart2 },
]

// ── Stepper UI ────────────────────────────────────────────────────────────────

function Stepper({ current }: { current: Step }) {
  return (
    <nav aria-label="Étapes de simulation">
      <ol className="flex items-center">
        {STEPS.map(({ id, label, Icon }, idx) => {
          const done = current > id
          const active = current === id
          return (
            <li key={id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-colors
                  ${done ? 'bg-solar-500 border-solar-500 text-white' : active ? 'bg-white border-solar-500 text-solar-600' : 'bg-white border-gray-300 text-gray-400'}`}
                  aria-current={active ? 'step' : undefined}
                >
                  {done ? <CheckCircle size={16} aria-hidden="true" /> : <Icon size={16} aria-hidden="true" />}
                </div>
                <span className={`text-xs font-medium hidden sm:block ${active ? 'text-solar-600' : done ? 'text-solar-500' : 'text-gray-400'}`}>
                  {label}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 mb-4 rounded ${current > id ? 'bg-solar-400' : 'bg-gray-200'}`} />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SimulatePage() {
  const [step, setStep] = useState<Step>(1)
  const [searchParams] = useSearchParams()

  const drawnPolygon = useSimulationStore((s) => s.drawnPolygon)
  const setDrawnPolygon = useSimulationStore((s) => s.setDrawnPolygon)
  const currentSimulation = useSimulationStore((s) => s.currentSimulation)
  const setCurrentSimulation = useSimulationStore((s) => s.setCurrentSimulation)
  const currentProject = useProjectStore((s) => s.currentProject)

  const projectId = searchParams.get('projectId') ?? currentProject?.id ?? ''

  const estimatedPanelCount = useMemo(() => {
    if (drawnPolygon === null) return 10
    return Math.max(1, Math.round(polygonAreaM2(drawnPolygon) / 2))
  }, [drawnPolygon])

  const { mutate: createSimulation, isPending } = useCreateSimulation()

  function handleFormSubmit(params: Omit<SimulationRequest, 'projectId'>) {
    if (projectId.length === 0) return
    createSimulation({ ...params, projectId }, { onSuccess: () => setStep(3) })
  }

  function handleNewSimulation() {
    setDrawnPolygon(null)
    setCurrentSimulation(null)
    setStep(1)
  }

  const mapCenter: [number, number] = currentProject !== null
    ? [currentProject.longitude, currentProject.latitude]
    : [-17.44, 14.69]

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Nouvelle simulation</h1>
        {currentProject !== null && (
          <p className="text-sm text-gray-500 mt-0.5">
            Projet : <span className="font-medium text-gray-700">{currentProject.name}</span>
          </p>
        )}
      </div>

      <Stepper current={step} />

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 sm:p-7">
        {/* Step 1 — Zone */}
        {step === 1 && (
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Définir la zone d'installation</h2>
              <p className="text-sm text-gray-500 mt-1">Dessinez un polygone pour délimiter la surface de toiture.</p>
            </div>
            <ArcGISMap showDrawTools onPolygonDraw={(c) => setDrawnPolygon(c)}
              height="380px" initialCenter={mapCenter} initialZoom={currentProject !== null ? 18 : 14} />
            {drawnPolygon !== null && (
              <div className="flex items-center gap-2 bg-solar-50 border border-solar-200 rounded-lg px-4 py-3 text-sm text-solar-800">
                <CheckCircle size={16} className="text-solar-500 shrink-0" aria-hidden="true" />
                <span>Zone tracée — environ <strong>{estimatedPanelCount} panneaux</strong> estimés
                  (≈ {Math.round(polygonAreaM2(drawnPolygon))} m²)</span>
              </div>
            )}
            <div className="flex justify-end pt-2">
              <button type="button" onClick={() => setStep(2)}
                className="rounded-xl bg-solar-500 hover:bg-solar-600 text-white font-semibold px-6 py-2.5 text-sm transition-colors">
                Suivant →
              </button>
            </div>
          </div>
        )}

        {/* Step 2 — Parameters */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Paramètres de simulation</h2>
              <p className="text-sm text-gray-500 mt-1">Renseignez les caractéristiques du système PV.</p>
            </div>
            {projectId.length === 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-800">
                Aucun projet sélectionné. Veuillez d'abord sélectionner un projet depuis le tableau de bord.
              </div>
            )}
            <SimulationForm projectId={projectId} initialPanelCount={estimatedPanelCount}
              isLoading={isPending} onSubmit={handleFormSubmit} />
            <button type="button" onClick={() => setStep(1)}
              className="rounded-xl border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium px-5 py-2.5 text-sm transition-colors">
              ← Retour
            </button>
          </div>
        )}

        {/* Step 3 — Results */}
        {step === 3 && (
          <div className="space-y-5">
            <h2 className="text-lg font-semibold text-gray-900">Résultats de simulation</h2>
            {currentSimulation !== null ? (
              <SimulationResults simulation={currentSimulation as SimulationFull}
                onNewSimulation={handleNewSimulation} />
            ) : (
              <p className="text-center py-12 text-gray-400 text-sm">
                Aucun résultat disponible. Veuillez relancer une simulation.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
