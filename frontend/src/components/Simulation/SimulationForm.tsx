import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import type { SimulationRequest } from '@/types/api'

// ── Constants ─────────────────────────────────────────────────────────────────

export const PANEL_MODELS = [
  { label: 'JA Solar JAM72S30 545W', powerWc: 545 },
  { label: 'Trina TSM-DE17M 545W', powerWc: 545 },
  { label: 'Canadian Solar HiKu7 600W', powerWc: 600 },
  { label: 'LONGI Hi-MO6 580W', powerWc: 580 },
] as const

const TARIFF_CODES = ['DPP', 'DMP', 'PPP', 'PMP', 'WOYOFAL'] as const

// ── Zod schema ────────────────────────────────────────────────────────────────

const schema = z.object({
  panelCount: z.number({ invalid_type_error: 'Nombre requis' }).int().min(1).max(10000),
  panelModel: z.string().min(1, 'Modèle requis'),
  panelPowerWc: z.number({ invalid_type_error: 'Puissance requise' }).int().min(100).max(1000),
  monthlyConsumptionKwh: z.number({ invalid_type_error: 'Consommation requise' }).min(1),
  tariffCode: z.enum(TARIFF_CODES),
  installationCostXof: z.number({ invalid_type_error: 'Coût requis' }).min(0),
  tilt: z.number().min(0).max(90),
  azimuth: z.number().min(0).max(360),
  systemLosses: z.number().min(0).max(1),
})

type FormValues = z.infer<typeof schema>

// ── Props ─────────────────────────────────────────────────────────────────────

interface SimulationFormProps {
  projectId: string
  initialPanelCount?: number
  isLoading: boolean
  onSubmit: (data: Omit<SimulationRequest, 'projectId'>) => void
}

// ── Field wrapper ─────────────────────────────────────────────────────────────

function Field({ id, label, error, children }: {
  id: string; label: string; error?: string | undefined; children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor={id}>{label}</label>
      {children}
      {error !== undefined && <p className="mt-1 text-xs text-red-600" id={`${id}-err`}>{error}</p>}
    </div>
  )
}

const inputCls = 'w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-solar-500 focus:ring-2 focus:ring-solar-200 outline-none'
const selectCls = `${inputCls} bg-white`

// ── Component ─────────────────────────────────────────────────────────────────

export default function SimulationForm({
  projectId: _projectId,
  initialPanelCount = 10,
  isLoading,
  onSubmit,
}: SimulationFormProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      panelCount: initialPanelCount,
      panelModel: PANEL_MODELS[0].label,
      panelPowerWc: PANEL_MODELS[0].powerWc,
      monthlyConsumptionKwh: 400,
      tariffCode: 'DPP',
      installationCostXof: 0,
      tilt: 15,
      azimuth: 180,
      systemLosses: 0.14,
    },
  })

  const selectedModel = watch('panelModel')

  function handleModelChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const model = PANEL_MODELS.find((m) => m.label === e.target.value)
    setValue('panelModel', e.target.value)
    if (model !== undefined) setValue('panelPowerWc', model.powerWc)
  }

  function handleFormSubmit(v: FormValues) {
    onSubmit({
      panelCount: v.panelCount, panelPowerWc: v.panelPowerWc, panelModel: v.panelModel,
      tilt: v.tilt, azimuth: v.azimuth, systemLosses: v.systemLosses,
      monthlyConsumptionKwh: v.monthlyConsumptionKwh,
      tariffCode: v.tariffCode, installationCostXof: v.installationCostXof,
    })
  }

  return (
    <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-5" noValidate>
      <Field id="panelCount" label="Nombre de panneaux" error={errors.panelCount?.message}>
        <input id="panelCount" type="number" {...register('panelCount', { valueAsNumber: true })}
          className={inputCls} aria-describedby={errors.panelCount ? 'panelCount-err' : undefined} />
      </Field>

      <Field id="panelModel" label="Modèle de panneau">
        <select id="panelModel" value={selectedModel} onChange={handleModelChange} className={selectCls}>
          {PANEL_MODELS.map((m) => <option key={m.label} value={m.label}>{m.label}</option>)}
        </select>
      </Field>

      <Field id="panelPowerWc" label="Puissance unitaire (Wc)" error={errors.panelPowerWc?.message}>
        <input id="panelPowerWc" type="number" {...register('panelPowerWc', { valueAsNumber: true })}
          className={inputCls} aria-describedby={errors.panelPowerWc ? 'panelPowerWc-err' : undefined} />
      </Field>

      <Field id="monthlyConsumptionKwh" label="Consommation mensuelle (kWh)" error={errors.monthlyConsumptionKwh?.message}>
        <input id="monthlyConsumptionKwh" type="number"
          {...register('monthlyConsumptionKwh', { valueAsNumber: true })}
          className={inputCls} aria-describedby={errors.monthlyConsumptionKwh ? 'monthlyConsumptionKwh-err' : undefined} />
      </Field>

      <Field id="tariffCode" label="Tarif SENELEC">
        <select id="tariffCode" {...register('tariffCode')} className={selectCls}>
          {TARIFF_CODES.map((t) => <option key={t} value={t}>{t === 'WOYOFAL' ? 'Woyofal' : t}</option>)}
        </select>
      </Field>

      <Field id="installationCostXof" label="Coût d'installation (FCFA)" error={errors.installationCostXof?.message}>
        <input id="installationCostXof" type="number"
          {...register('installationCostXof', { valueAsNumber: true })}
          className={inputCls} aria-describedby={errors.installationCostXof ? 'installationCostXof-err' : undefined} />
      </Field>

      {/* Advanced section */}
      <div className="border border-gray-200 rounded-lg overflow-hidden">
        <button type="button" onClick={() => setAdvancedOpen((v) => !v)} aria-expanded={advancedOpen}
          className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors">
          <span>Paramètres avancés</span>
          {advancedOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {advancedOpen && (
          <div className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[
              { id: 'tilt', label: 'Inclinaison (°)', min: 0, max: 90, step: 1 },
              { id: 'azimuth', label: 'Azimut (°)', min: 0, max: 360, step: 1 },
              { id: 'systemLosses', label: 'Pertes système', min: 0, max: 1, step: 0.01 },
            ].map(({ id, label, min, max, step }) => (
              <div key={id}>
                <label className="block text-xs font-medium text-gray-600 mb-1" htmlFor={id}>{label}</label>
                <input id={id} type="number" min={min} max={max} step={step}
                  {...register(id as 'tilt' | 'azimuth' | 'systemLosses', { valueAsNumber: true })}
                  className={inputCls} />
              </div>
            ))}
          </div>
        )}
      </div>

      <button type="submit" disabled={isLoading}
        className="w-full flex items-center justify-center gap-2 rounded-xl bg-solar-500 hover:bg-solar-600 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold py-3 text-sm transition-colors">
        {isLoading && <Loader2 size={16} className="animate-spin" aria-hidden="true" />}
        {isLoading ? 'Simulation en cours...' : 'Lancer la simulation'}
      </button>
    </form>
  )
}
