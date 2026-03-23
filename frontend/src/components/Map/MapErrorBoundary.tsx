import { Component } from 'react'
import type { ReactNode, ErrorInfo } from 'react'

// ── MapErrorBoundary ──────────────────────────────────────────────────────────
// ArcGIS SDK can throw during WebGL initialisation; this catches those errors
// gracefully instead of crashing the entire page.

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  message: string
}

export class MapErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, message: '' }
  }

  static getDerivedStateFromError(error: unknown): State {
    const message =
      error instanceof Error ? error.message : 'Erreur inconnue de la carte'
    return { hasError: true, message }
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[MapErrorBoundary]', error, info.componentStack)
  }

  override render() {
    if (this.state.hasError) {
      if (this.props.fallback !== undefined) {
        return this.props.fallback
      }
      return (
        <div className="map-error flex flex-col items-center justify-center rounded-xl border border-red-200 bg-red-50 p-8 text-center">
          <div className="mb-3 text-3xl" aria-hidden="true">🗺️</div>
          <p className="font-semibold text-red-700">Impossible de charger la carte</p>
          <p className="mt-1 text-sm text-red-500">{this.state.message}</p>
          <p className="mt-2 text-xs text-red-400">
            Vérifiez que WebGL est activé dans votre navigateur.
          </p>
        </div>
      )
    }
    return this.props.children
  }
}
