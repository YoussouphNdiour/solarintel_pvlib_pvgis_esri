import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { apiClient, tokenStorage } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import type {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserResponse,
} from '@/types/api'

// ── Query Keys ────────────────────────────────────────────────────────────────

export const authKeys = {
  me: () => ['auth', 'me'] as const,
}

// ── useLogin ──────────────────────────────────────────────────────────────────

export function useLogin() {
  const { setTokens } = useAuthStore()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const { data } = await apiClient.post<TokenResponse>(
        '/auth/login',
        credentials,
      )
      return data
    },
    onSuccess: async (tokenData) => {
      // Backend returns snake_case: access_token / refresh_token
      const accessToken = (tokenData as any).access_token ?? tokenData.accessToken
      const refreshToken = (tokenData as any).refresh_token ?? tokenData.refreshToken
      // Save to the key the axios interceptor reads from
      tokenStorage.setAccessToken(accessToken)
      tokenStorage.setRefreshToken(refreshToken)
      // Fetch user profile (interceptor now has the token)
      const { data: user } = await apiClient.get<UserResponse>('/auth/me')
      setTokens(accessToken, refreshToken, user)
      void queryClient.invalidateQueries({ queryKey: authKeys.me() })
      toast.success('Connexion réussie')
      navigate('/dashboard', { replace: true })
    },
    onError: () => {
      toast.error('Email ou mot de passe incorrect')
    },
  })
}

// ── useRegister ───────────────────────────────────────────────────────────────

export function useRegister() {
  const navigate = useNavigate()

  return useMutation({
    mutationFn: async (payload: RegisterRequest) => {
      const { data } = await apiClient.post<UserResponse>(
        '/auth/register',
        payload,
      )
      return data
    },
    onSuccess: () => {
      toast.success('Compte créé avec succès ! Connectez-vous.')
      navigate('/login', { replace: true })
    },
    onError: () => {
      toast.error('Erreur lors de la création du compte')
    },
  })
}

// ── useMe ─────────────────────────────────────────────────────────────────────

export function useMe() {
  const { isAuthenticated, setUser } = useAuthStore()

  const query = useQuery({
    queryKey: authKeys.me(),
    queryFn: async () => {
      const { data } = await apiClient.get<UserResponse>('/auth/me')
      return data
    },
    enabled: isAuthenticated,
  })

  // Sync fresh user data into the auth store whenever the query succeeds
  useEffect(() => {
    if (query.data !== undefined) {
      setUser(query.data)
    }
  }, [query.data, setUser])

  return query
}

// ── useLogout ─────────────────────────────────────────────────────────────────

export function useLogout() {
  const { clearAuth } = useAuthStore()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return () => {
    tokenStorage.clearAll()
    clearAuth()
    queryClient.clear()
    toast.success('Déconnecté')
    navigate('/login', { replace: true })
  }
}
