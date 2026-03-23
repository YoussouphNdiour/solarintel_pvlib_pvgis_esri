import { useEffect, useRef } from 'react'
import { MapErrorBoundary } from './MapErrorBoundary'

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ArcGISMapProps {
  initialCenter?: [number, number]  // [lng, lat], defaults to Dakar
  initialZoom?: number
  onLocationSelect?: (lat: number, lng: number, address?: string) => void
  onPolygonDraw?: (coordinates: number[][]) => void
  showDrawTools?: boolean
  height?: string
}

// ── Inner map (loaded dynamically to avoid blocking initial render) ────────────

function ArcGISMapInner({
  initialCenter = [-17.44, 14.69],
  initialZoom = 12,
  onLocationSelect,
  onPolygonDraw,
  showDrawTools = false,
  height = '400px',
}: ArcGISMapProps) {
  const mapRef = useRef<HTMLDivElement>(null)
  const cleanupRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (mapRef.current === null) return

    const container = mapRef.current
    let cancelled = false

    void (async () => {
      try {
        const [
          { default: esriConfig },
          { default: Map },
          { default: MapView },
          { default: Search },
        ] = await Promise.all([
          import('@arcgis/core/config'),
          import('@arcgis/core/Map'),
          import('@arcgis/core/views/MapView'),
          import('@arcgis/core/widgets/Search'),
        ])

        const arcgisKey = import.meta.env['VITE_ARCGIS_API_KEY'] as string | undefined
        if (arcgisKey) {
          esriConfig.apiKey = arcgisKey
        }

        if (cancelled) return

        const map = new Map({ basemap: 'satellite' })

        const view = new MapView({
          container,
          map,
          center: initialCenter,
          zoom: initialZoom,
        })

        // Search / geocoder widget
        const searchWidget = new Search({ view })
        view.ui.add(searchWidget, 'top-right')

        // Click handler for location selection
        if (onLocationSelect !== undefined) {
          view.on('click', (event) => {
            const point = event.mapPoint
            if (point === null || point === undefined) return
            const lat = point.latitude
            const lng = point.longitude

            void (async () => {
              try {
                const { locationToAddress } = await import(
                  '@arcgis/core/rest/locator'
                )
                const result = await locationToAddress(
                  'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer',
                  { location: point },
                )
                onLocationSelect(lat, lng, result.address ?? undefined)
              } catch {
                onLocationSelect(lat, lng)
              }
            })()
          })
        }

        // Draw tools (Sketch widget)
        if (showDrawTools && onPolygonDraw !== undefined) {
          const [
            { default: GraphicsLayer },
            { default: Sketch },
          ] = await Promise.all([
            import('@arcgis/core/layers/GraphicsLayer'),
            import('@arcgis/core/widgets/Sketch'),
          ])

          if (cancelled) return

          const graphicsLayer = new GraphicsLayer()
          map.add(graphicsLayer)

          const sketch = new Sketch({
            layer: graphicsLayer,
            view,
            creationMode: 'single',
            availableCreateTools: ['polygon'],
          })

          view.ui.add(sketch, 'top-left')

          sketch.on('create', (event) => {
            if (event.state === 'complete') {
              const geometry = event.graphic.geometry
              if (geometry === null || geometry === undefined) return
              if (geometry.type === 'polygon') {
                // Cast through unknown: Polygon has rings but base Geometry type doesn't
                const polygon = geometry as unknown as { rings: number[][][] }
                const ring = polygon.rings[0]
                if (ring !== undefined) {
                  onPolygonDraw(ring)
                }
              }
            }
          })
        }

        cleanupRef.current = () => {
          view.destroy()
        }
      } catch (err) {
        if (!cancelled) {
          console.error('[ArcGISMap] Initialisation error:', err)
          // Re-throw so the error boundary catches it
          throw err
        }
      }
    })()

    return () => {
      cancelled = true
      cleanupRef.current?.()
      cleanupRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div
      ref={mapRef}
      style={{ height }}
      className="arcgis-map w-full overflow-hidden rounded-xl"
      role="application"
      aria-label="Carte interactive ArcGIS"
    />
  )
}

// ── ArcGISMap (with error boundary) ──────────────────────────────────────────

export default function ArcGISMap(props: ArcGISMapProps) {
  return (
    <MapErrorBoundary>
      <ArcGISMapInner {...props} />
    </MapErrorBoundary>
  )
}
