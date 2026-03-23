import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

// ── UI Store ──────────────────────────────────────────────────────────────────

interface UIState {
  sidebarOpen: boolean
  language: 'fr' | 'wo'
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setLanguage: (lang: 'fr' | 'wo') => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      language: 'fr',
      toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      setLanguage: (lang) => set({ language: lang }),
    }),
    {
      name: 'solarintel-ui',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sidebarOpen: state.sidebarOpen,
        language: state.language,
      }),
    },
  ),
)
