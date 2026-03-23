import { useState } from 'react'
import ArcGISMap from './ArcGISMap'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SelectedLocation {
  lat: number
  lng: number
  address?: string
}

interface LocationPickerProps {
  onLocationChange: (location: SelectedLocation) => void
  initialLocation?: SelectedLocation
  height?: string
}

// ── LocationPicker ────────────────────────────────────────────────────────────

export default function LocationPicker({
  onLocationChange,
  initialLocation,
  height = '300px',
}: LocationPickerProps) {
  const [selected, setSelected] = useState<SelectedLocation | null>(
    initialLocation ?? null,
  )
  const [isLocating, setIsLocating] = useState(false)
  const [geoError, setGeoError] = useState<string | null>(null)

  const handleLocationSelect = (lat: number, lng: number, address?: string) => {
    const location: SelectedLocation = address !== undefined
      ? { lat, lng, address }
      : { lat, lng }
    setSelected(location)
    onLocationChange(location)
  }

  const handleUseMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoError("La géolocalisation n'est pas supportée par votre navigateur.")
      return
    }

    setIsLocating(true)
    setGeoError(null)

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const location: SelectedLocation = {
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        }
        setSelected(location)
        onLocationChange(location)
        setIsLocating(false)
      },
      (error) => {
        const messages: Record<number, string> = {
          1: 'Permission de géolocalisation refusée.',
          2: 'Position indisponible.',
          3: "Délai d'attente dépassé.",
        }
        setGeoError(messages[error.code] ?? 'Erreur de géolocalisation.')
        setIsLocating(false)
      },
      { timeout: 10_000, maximumAge: 60_000 },
    )
  }

  const initialCenter: [number, number] | undefined =
    initialLocation !== undefined
      ? [initialLocation.lng, initialLocation.lat]
      : undefined

  return (
    <div className="location-picker space-y-3">
      {/* Map */}
      <ArcGISMap
        {...(initialCenter !== undefined && { initialCenter })}
        onLocationSelect={handleLocationSelect}
        height={height}
      />

      {/* Controls */}
      <div className="flex items-start justify-between gap-3">
        {/* Selected coordinates */}
        {selected !== null ? (
          <div className="flex-1 rounded-lg bg-solar-50 px-3 py-2 text-sm">
            <p className="font-medium text-solar-800">Localisation sélectionnée</p>
            <p className="mt-0.5 font-mono text-xs text-solar-600">
              {selected.lat.toFixed(6)}, {selected.lng.toFixed(6)}
            </p>
            {selected.address !== undefined && (
              <p className="mt-0.5 text-xs text-gray-600 truncate">
                {selected.address}
              </p>
            )}
          </div>
        ) : (
          <p className="flex-1 text-sm text-gray-400">
            Cliquez sur la carte pour sélectionner une localisation
          </p>
        )}

        {/* Geolocation button */}
        <button
          type="button"
          onClick={handleUseMyLocation}
          disabled={isLocating}
          className="flex shrink-0 items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          aria-label="Utiliser ma position actuelle"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
          </svg>
          {isLocating ? 'Localisation...' : 'Ma position'}
        </button>
      </div>

      {/* Geolocation error */}
      {geoError !== null && (
        <p className="text-xs text-red-600" role="alert">{geoError}</p>
      )}
    </div>
  )
}
