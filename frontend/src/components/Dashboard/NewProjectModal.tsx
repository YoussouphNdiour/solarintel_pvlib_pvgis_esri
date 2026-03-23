import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useCreateProject } from '@/hooks/useProjects'
import LocationPicker from '@/components/Map/LocationPicker'
import type { SelectedLocation } from '@/components/Map/LocationPicker'

// ── Schema ────────────────────────────────────────────────────────────────────

const newProjectSchema = z.object({
  name: z.string().min(2, 'Le nom doit contenir au moins 2 caractères'),
  description: z.string().optional(),
  address: z.string().optional(),
  latitude: z.number({ required_error: 'Sélectionnez une localisation sur la carte' }),
  longitude: z.number({ required_error: 'Sélectionnez une localisation sur la carte' }),
})

type NewProjectFormValues = z.infer<typeof newProjectSchema>

// ── NewProjectModal ───────────────────────────────────────────────────────────

interface NewProjectModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function NewProjectModal({ isOpen, onClose }: NewProjectModalProps) {
  const createProject = useCreateProject()

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    reset,
    formState: { errors },
  } = useForm<NewProjectFormValues>({
    resolver: zodResolver(newProjectSchema),
  })

  const latitude = watch('latitude')
  const longitude = watch('longitude')

  // Reset form when modal closes
  useEffect(() => {
    if (!isOpen) reset()
  }, [isOpen, reset])

  const handleLocationChange = (location: SelectedLocation) => {
    setValue('latitude', location.lat, { shouldValidate: true })
    setValue('longitude', location.lng, { shouldValidate: true })
    if (location.address !== undefined) {
      setValue('address', location.address)
    }
  }

  const onSubmit = (values: NewProjectFormValues) => {
    createProject.mutate(
      {
        name: values.name,
        ...(values.description !== undefined && values.description.length > 0 && { description: values.description }),
        latitude: values.latitude,
        longitude: values.longitude,
        ...(values.address !== undefined && values.address.length > 0 && { address: values.address }),
      },
      { onSuccess: onClose },
    )
  }

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="new-project-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <h2 id="new-project-title" className="text-lg font-semibold text-gray-900">
            Nouveau projet
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            aria-label="Fermer la fenêtre"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="px-6 py-5 space-y-5">
          {/* Name */}
          <div>
            <label htmlFor="proj-name" className="block text-sm font-medium text-gray-700">
              Nom du projet *
            </label>
            <input
              id="proj-name"
              type="text"
              {...register('name')}
              className={`mt-1 block w-full rounded-lg border px-3 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-solar-500 ${errors.name !== undefined ? 'border-red-400 bg-red-50' : 'border-gray-300'}`}
              placeholder="Centrale PV résidentielle Dakar"
              aria-invalid={errors.name !== undefined}
            />
            {errors.name !== undefined && (
              <p className="mt-1 text-xs text-red-600" role="alert">{errors.name.message}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label htmlFor="proj-desc" className="block text-sm font-medium text-gray-700">
              Description
            </label>
            <textarea
              id="proj-desc"
              rows={2}
              {...register('description')}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-solar-500"
              placeholder="Description optionnelle..."
            />
          </div>

          {/* Location picker */}
          <div>
            <p className="mb-2 block text-sm font-medium text-gray-700">
              Localisation * — cliquez sur la carte
            </p>
            <LocationPicker
              onLocationChange={handleLocationChange}
              height="280px"
            />
            {(errors.latitude !== undefined || errors.longitude !== undefined) && (
              <p className="mt-1 text-xs text-red-600" role="alert">
                {errors.latitude?.message ?? errors.longitude?.message}
              </p>
            )}
            {latitude !== undefined && longitude !== undefined && (
              <p className="mt-1 font-mono text-xs text-gray-500">
                {latitude.toFixed(6)}, {longitude.toFixed(6)}
              </p>
            )}
          </div>

          {/* API error */}
          {createProject.isError && (
            <div className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
              Erreur lors de la création du projet. Veuillez réessayer.
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-gray-300 px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={createProject.isPending}
              className="rounded-lg bg-solar-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-solar-600 disabled:opacity-60"
              aria-label="Créer le projet"
            >
              {createProject.isPending ? 'Création...' : 'Créer le projet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
