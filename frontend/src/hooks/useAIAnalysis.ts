import { useCallback, useRef, useState } from 'react'
import { tokenStorage } from '@/api/client'
import type {
  AnalysisResult,
  EquipmentRecommendation,
  SSEEvent,
} from '@/types/api'

// ── Types ─────────────────────────────────────────────────────────────────────

type AgentStatus = 'idle' | 'running' | 'done' | 'error'

interface UseAIAnalysisReturn {
  isRunning: boolean
  agentStatuses: Record<string, AgentStatus>
  narrative: string
  equipmentRec: EquipmentRecommendation | null
  qaResults: AnalysisResult['qaResults'] | null
  finalResult: AnalysisResult | null
  errors: string[]
  startAnalysis: (simulationId: string) => void
  reset: () => void
}

// ── Base URL (mirrors api/client.ts) ─────────────────────────────────────────

const BASE_URL =
  (import.meta.env['VITE_API_BASE_URL'] as string | undefined) ??
  'http://localhost:8000'

// ── SSE line parser ───────────────────────────────────────────────────────────

function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith('data: ')) return null
  const raw = line.slice(6).trim()
  if (raw === '' || raw === '[DONE]') return null
  try {
    return JSON.parse(raw) as SSEEvent
  } catch {
    return null
  }
}

// ── Hook ──────────────────────────────────────────────────────────────────────

const INITIAL_STATUSES: Record<string, AgentStatus> = {
  dimensionnement: 'idle',
  report_writer: 'idle',
  qa: 'idle',
}

export function useAIAnalysis(): UseAIAnalysisReturn {
  const [isRunning, setIsRunning] = useState(false)
  const [agentStatuses, setAgentStatuses] =
    useState<Record<string, AgentStatus>>(INITIAL_STATUSES)
  const [narrative, setNarrative] = useState('')
  const [equipmentRec, setEquipmentRec] =
    useState<EquipmentRecommendation | null>(null)
  const [qaResults, setQaResults] =
    useState<AnalysisResult['qaResults'] | null>(null)
  const [finalResult, setFinalResult] = useState<AnalysisResult | null>(null)
  const [errors, setErrors] = useState<string[]>([])

  const abortRef = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsRunning(false)
    setAgentStatuses(INITIAL_STATUSES)
    setNarrative('')
    setEquipmentRec(null)
    setQaResults(null)
    setFinalResult(null)
    setErrors([])
  }, [])

  const startAnalysis = useCallback((simulationId: string) => {
    // Cancel any in-flight request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsRunning(true)
    setAgentStatuses(INITIAL_STATUSES)
    setNarrative('')
    setEquipmentRec(null)
    setQaResults(null)
    setFinalResult(null)
    setErrors([])

    void (async () => {
      try {
        const token = tokenStorage.getAccessToken()
        const response = await fetch(
          `${BASE_URL}/api/v2/ai/analyze`,
          {
            method: 'POST',
            signal: controller.signal,
            headers: {
              'Content-Type': 'application/json',
              Accept: 'text/event-stream',
              ...(token !== null
                ? { Authorization: `Bearer ${token}` }
                : {}),
            },
            body: JSON.stringify({ simulationId }),
          },
        )

        if (!response.ok) {
          const msg = `HTTP ${response.status}: ${response.statusText}`
          setErrors((prev) => [...prev, msg])
          setIsRunning(false)
          return
        }

        if (response.body === null) {
          setErrors((prev) => [...prev, 'Réponse vide du serveur'])
          setIsRunning(false)
          return
        }

        // Stream the body using ReadableStream + TextDecoderStream
        const reader = response.body
          .pipeThrough(new TextDecoderStream())
          .getReader()

        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += value

          // Split on double-newline (SSE event boundary) but process
          // individual data: lines immediately
          const lines = buffer.split('\n')
          // Keep incomplete last line in buffer
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (trimmed === '') continue
            const event = parseSSELine(trimmed)
            if (event === null) continue

            switch (event.type) {
              case 'status':
                setAgentStatuses((prev) => ({
                  ...prev,
                  [event.agent]: event.status,
                }))
                break

              case 'narrative_token':
                setNarrative((prev) => prev + event.token)
                break

              case 'agent_result': {
                if (
                  event.agent === 'dimensionnement' &&
                  event.data !== null &&
                  typeof event.data === 'object'
                ) {
                  setEquipmentRec(event.data as EquipmentRecommendation)
                }
                if (
                  event.agent === 'qa' &&
                  event.data !== null &&
                  typeof event.data === 'object'
                ) {
                  setQaResults(event.data as AnalysisResult['qaResults'])
                }
                break
              }

              case 'complete':
                setFinalResult(event.analysis)
                setEquipmentRec(event.analysis.equipmentRecommendation)
                setQaResults(event.analysis.qaResults)
                setNarrative(event.analysis.reportNarrative)
                setAgentStatuses({
                  dimensionnement: 'done',
                  report_writer: 'done',
                  qa: 'done',
                })
                setIsRunning(false)
                break

              case 'error':
                setErrors((prev) => [...prev, event.message])
                break
            }
          }
        }

        setIsRunning(false)
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === 'AbortError') {
          // Intentional abort — do not surface as error
          return
        }
        const msg =
          err instanceof Error ? err.message : 'Erreur réseau inconnue'
        setErrors((prev) => [...prev, msg])
        setIsRunning(false)
      }
    })()
  }, [])

  return {
    isRunning,
    agentStatuses,
    narrative,
    equipmentRec,
    qaResults,
    finalResult,
    errors,
    startAnalysis,
    reset,
  }
}
