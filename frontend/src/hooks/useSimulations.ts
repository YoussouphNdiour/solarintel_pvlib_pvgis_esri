import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { apiClient } from '@/api/client'
import { useSimulationStore } from '@/stores/simulationStore'
import type {
  CursorPage,
  Simulation,
  SimulationFull,
  SimulationRequest,
} from '@/types/api'

// ── Query Keys ────────────────────────────────────────────────────────────────

export const simulationKeys = {
  all: () => ['simulations'] as const,
  byProject: (projectId: string) =>
    [...simulationKeys.all(), 'project', projectId] as const,
  detail: (id: string) => [...simulationKeys.all(), 'detail', id] as const,
}

// ── useSimulations (list by project) ─────────────────────────────────────────

export function useSimulations(projectId: string) {
  return useQuery({
    queryKey: simulationKeys.byProject(projectId),
    queryFn: async () => {
      const { data } = await apiClient.get<CursorPage<Simulation>>(
        '/simulate',
        { params: { project_id: projectId, limit: '20' } },
      )
      return data
    },
    enabled: projectId.length > 0,
  })
}

// ── useSimulation (single) ────────────────────────────────────────────────────

export function useSimulation(id: string) {
  return useQuery({
    queryKey: simulationKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<SimulationFull>(`/simulate/${id}`)
      return data
    },
    enabled: id.length > 0,
  })
}

// ── useCreateSimulation ───────────────────────────────────────────────────────

export function useCreateSimulation() {
  const queryClient = useQueryClient()
  const setCurrentSimulation = useSimulationStore(
    (s) => s.setCurrentSimulation,
  )

  return useMutation({
    mutationFn: async (payload: SimulationRequest) => {
      const { data } = await apiClient.post<SimulationFull>('/simulate', payload)
      return data
    },
    onSuccess: (result) => {
      void queryClient.invalidateQueries({
        queryKey: simulationKeys.byProject(result.projectId),
      })
      queryClient.setQueryData(simulationKeys.detail(result.id), result)
      setCurrentSimulation(result)
      toast.success('Simulation terminée avec succès')
    },
    onError: () => {
      toast.error('Erreur lors de la simulation. Veuillez réessayer.')
    },
  })
}
