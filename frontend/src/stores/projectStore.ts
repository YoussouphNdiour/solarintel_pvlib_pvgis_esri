import { create } from 'zustand'
import type { Project } from '@/types/api'

// ── Project Store ─────────────────────────────────────────────────────────────

interface ProjectState {
  currentProject: Project | null
  setCurrentProject: (p: Project | null) => void
}

export const useProjectStore = create<ProjectState>()((set) => ({
  currentProject: null,
  setCurrentProject: (p) => set({ currentProject: p }),
}))
