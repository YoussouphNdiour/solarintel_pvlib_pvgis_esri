import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { UserResponse } from '@/types/api'

// ── Auth Store ────────────────────────────────────────────────────────────────

interface AuthState {
  user: UserResponse | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  setTokens: (access: string, refresh: string, user: UserResponse) => void
  clearAuth: () => void
  setUser: (user: UserResponse) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      setTokens: (access, refresh, user) => {
        set({
          accessToken: access,
          refreshToken: refresh,
          user,
          isAuthenticated: true,
        })
      },

      clearAuth: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        })
      },

      setUser: (user) => {
        set({ user })
      },
    }),
    {
      name: 'solarintel-auth',
      storage: createJSONStorage(() => localStorage),
      // Only persist tokens and user; isAuthenticated is derived on rehydration
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    },
  ),
)
