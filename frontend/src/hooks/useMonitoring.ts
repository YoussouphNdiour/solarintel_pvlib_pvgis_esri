import { useCallback, useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { apiClient } from '@/api/client'
import { tokenStorage } from '@/api/client'
import type {
  MonitoringHistoryResponse,
  MonitoringReading,
  MonthlyComparison,
  ProductionStats,
  WSMonitoringEvent,
} from '@/types/api'

// ── Query Keys ────────────────────────────────────────────────────────────────

export const monitoringKeys = {
  all: () => ['monitoring'] as const,
  stats: (projectId: string) =>
    [...monitoringKeys.all(), projectId, 'stats'] as const,
  history: (projectId: string) =>
    [...monitoringKeys.all(), projectId, 'history'] as const,
  monthly: (projectId: string) =>
    [...monitoringKeys.all(), projectId, 'monthly'] as const,
}

// ── useMonitoringStats ────────────────────────────────────────────────────────

export function useMonitoringStats(projectId: string) {
  return useQuery({
    queryKey: monitoringKeys.stats(projectId),
    queryFn: async () => {
      const { data } = await apiClient.get<ProductionStats>(
        `/monitoring/${projectId}/stats`,
      )
      return data
    },
    enabled: projectId.length > 0,
    refetchInterval: 30_000,
  })
}

// ── useMonitoringHistory ──────────────────────────────────────────────────────

export function useMonitoringHistory(projectId: string) {
  return useInfiniteQuery({
    queryKey: monitoringKeys.history(projectId),
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = { limit: '50' }
      if (typeof pageParam === 'string') {
        params['cursor'] = pageParam
      }
      const { data } = await apiClient.get<MonitoringHistoryResponse>(
        `/monitoring/${projectId}/history`,
        { params },
      )
      return data
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
    enabled: projectId.length > 0,
  })
}

// ── useMonthlyComparison ──────────────────────────────────────────────────────

export function useMonthlyComparison(projectId: string) {
  return useQuery({
    queryKey: monitoringKeys.monthly(projectId),
    queryFn: async () => {
      const { data } = await apiClient.get<MonthlyComparison[]>(
        `/monitoring/${projectId}/monthly`,
        { params: { months: '12' } },
      )
      return data
    },
    enabled: projectId.length > 0,
  })
}

// ── useMonitoringWebSocket ────────────────────────────────────────────────────

const BASE_URL = import.meta.env['VITE_API_BASE_URL'] ?? 'http://localhost:8000'
const MAX_READINGS = 100
const MAX_BACKOFF_MS = 30_000

interface WSMonitoringState {
  stats: ProductionStats | null
  latestReading: MonitoringReading | null
  readings: MonitoringReading[]
  alerts: Array<{ message: string; receivedAt: string }>
  isConnected: boolean
  reconnectAttempts: number
}

export function useMonitoringWebSocket(projectId: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const attemptsRef = useRef(0)
  const isMountedRef = useRef(true)

  const [state, setState] = useState<WSMonitoringState>({
    stats: null,
    latestReading: null,
    readings: [],
    alerts: [],
    isConnected: false,
    reconnectAttempts: 0,
  })

  const connect = useCallback(() => {
    if (!isMountedRef.current || projectId.length === 0) return

    const token = tokenStorage.getAccessToken()
    const wsBase = BASE_URL.replace(/^http/, 'ws')
    const url = `${wsBase}/api/v2/monitoring/${projectId}/ws${token ? `?token=${token}` : ''}`

    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (!isMountedRef.current) return
      attemptsRef.current = 0
      setState((prev) => ({
        ...prev,
        isConnected: true,
        reconnectAttempts: 0,
      }))
    }

    ws.onmessage = (event: MessageEvent) => {
      if (!isMountedRef.current) return
      let parsed: WSMonitoringEvent
      try {
        parsed = JSON.parse(event.data as string) as WSMonitoringEvent
      } catch {
        return
      }

      switch (parsed.type) {
        case 'stats':
          setState((prev) => ({ ...prev, stats: parsed.data }))
          break
        case 'reading':
          setState((prev) => ({
            ...prev,
            latestReading: parsed.data,
            readings: [parsed.data, ...prev.readings].slice(0, MAX_READINGS),
          }))
          break
        case 'alert':
          toast.error(parsed.data.message)
          setState((prev) => ({
            ...prev,
            alerts: [
              { message: parsed.data.message, receivedAt: new Date().toISOString() },
              ...prev.alerts,
            ].slice(0, 50),
          }))
          break
        case 'ping':
          // keep-alive — no state change needed
          break
      }
    }

    ws.onclose = () => {
      if (!isMountedRef.current) return
      setState((prev) => ({ ...prev, isConnected: false }))
      scheduleReconnect()
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [projectId])

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current) return
    attemptsRef.current += 1
    const delay = Math.min(1000 * 2 ** (attemptsRef.current - 1), MAX_BACKOFF_MS)
    setState((prev) => ({
      ...prev,
      reconnectAttempts: attemptsRef.current,
    }))
    reconnectTimerRef.current = setTimeout(() => {
      if (isMountedRef.current) connect()
    }, delay)
  }, [connect])

  const forceReconnect = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    wsRef.current?.close()
    attemptsRef.current = 0
    connect()
  }, [connect])

  useEffect(() => {
    isMountedRef.current = true
    if (projectId.length > 0) connect()

    return () => {
      isMountedRef.current = false
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current)
      }
      wsRef.current?.close()
    }
  }, [projectId, connect])

  return {
    stats: state.stats,
    latestReading: state.latestReading,
    readings: state.readings,
    alerts: state.alerts,
    isConnected: state.isConnected,
    reconnectAttempts: state.reconnectAttempts,
    forceReconnect,
  }
}
