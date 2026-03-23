// ── useIntegrations — Sprint 6 integration hooks ──────────────────────────────

import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { apiClient } from '@/api/client'
import { getEquipmentPrices } from '@/api/client'
import type {
  InverterPrice,
  PanelPrice,
  SendReportWhatsAppRequest,
  WeatherCorrection,
} from '@/types/api'

// ── Query keys ────────────────────────────────────────────────────────────────

export const integrationKeys = {
  weather: (projectId: string) => ['weather-correction', projectId] as const,
  equipmentPrices: () => ['equipment-prices'] as const,
}

// ── useWeatherCorrection ──────────────────────────────────────────────────────
// GET /api/v2/webhooks/weather/{projectId}
// Fetches the latest weather correction factor for the project site.
// Only enabled when projectId is a non-empty string.

export function useWeatherCorrection(projectId: string) {
  return useQuery({
    queryKey: integrationKeys.weather(projectId),
    queryFn: async () => {
      const { data } = await apiClient.get<WeatherCorrection>(
        `/webhooks/weather/${projectId}`,
      )
      return data
    },
    enabled: projectId.length > 0,
    // Weather corrections are fetched fresh each time the badge mounts; they
    // can change throughout the day. Treat as stale immediately.
    staleTime: 0,
    // Never throw to the React error boundary — the badge handles errors silently.
    retry: false,
  })
}

// ── useSendReportWhatsApp ─────────────────────────────────────────────────────
// POST /api/v2/webhooks/whatsapp/send-report
// Sends a generated PDF report to a WhatsApp number.

export function useSendReportWhatsApp() {
  return useMutation({
    mutationFn: async (payload: SendReportWhatsAppRequest) => {
      const { data } = await apiClient.post<{ messageId: string }>(
        '/webhooks/whatsapp/send-report',
        payload,
      )
      return data
    },
    onSuccess: (_data, variables) => {
      // Format the last digits for the confirmation message
      const digits = variables.phone.replace(/\s/g, '')
      toast.success(`Rapport envoyé sur WhatsApp ✓ (+221 ${digits})`)
    },
    onError: () => {
      toast.error('Échec envoi WhatsApp — vérifiez le numéro')
    },
  })
}

// ── useEquipmentPrices ────────────────────────────────────────────────────────
// GET /api/v2/equipment/prices
// Returns Senegalese supplier market prices for panels and inverters.
// Prices refresh weekly so we cache for 24 h.

export function useEquipmentPrices() {
  return useQuery<{ panels: PanelPrice[]; inverters: InverterPrice[] }>({
    queryKey: integrationKeys.equipmentPrices(),
    queryFn: async () => {
      const { data } = await getEquipmentPrices()
      return data
    },
    staleTime: 1000 * 60 * 60 * 24, // 24 h
  })
}
