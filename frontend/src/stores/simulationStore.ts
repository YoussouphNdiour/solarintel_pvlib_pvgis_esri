import { create } from 'zustand'
import type { Simulation } from '@/types/api'

// ── Simulation Store ──────────────────────────────────────────────────────────

interface SimulationState {
  currentSimulation: Simulation | null
  drawnPolygon: number[][] | null // [[lng, lat], ...]
  setCurrentSimulation: (s: Simulation | null) => void
  setDrawnPolygon: (coords: number[][] | null) => void
}

export const useSimulationStore = create<SimulationState>()((set) => ({
  currentSimulation: null,
  drawnPolygon: null,
  setCurrentSimulation: (s) => set({ currentSimulation: s }),
  setDrawnPolygon: (coords) => set({ drawnPolygon: coords }),
}))
