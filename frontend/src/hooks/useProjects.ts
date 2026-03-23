import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { apiClient } from '@/api/client'
import type {
  CreateProjectRequest,
  CursorPage,
  Project,
} from '@/types/api'

// ── Query Keys ────────────────────────────────────────────────────────────────

export const projectKeys = {
  all: () => ['projects'] as const,
  lists: () => [...projectKeys.all(), 'list'] as const,
  detail: (id: string) => [...projectKeys.all(), 'detail', id] as const,
}

// ── useProjects ───────────────────────────────────────────────────────────────

export function useProjects() {
  return useInfiniteQuery({
    queryKey: projectKeys.lists(),
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = { limit: '20' }
      if (typeof pageParam === 'string') {
        params['cursor'] = pageParam
      }
      const { data } = await apiClient.get<CursorPage<Project>>('/projects', {
        params,
      })
      return data
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.nextCursor ?? undefined,
  })
}

// ── useProject ────────────────────────────────────────────────────────────────

export function useProject(id: string) {
  return useQuery({
    queryKey: projectKeys.detail(id),
    queryFn: async () => {
      const { data } = await apiClient.get<Project>(`/projects/${id}`)
      return data
    },
    enabled: id.length > 0,
  })
}

// ── useCreateProject ──────────────────────────────────────────────────────────

export function useCreateProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: CreateProjectRequest) => {
      const { data } = await apiClient.post<Project>('/projects', payload)
      return data
    },
    onSuccess: (newProject) => {
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
      // Seed the detail cache immediately
      queryClient.setQueryData(projectKeys.detail(newProject.id), newProject)
      toast.success('Projet créé avec succès')
    },
    onError: () => {
      toast.error('Erreur lors de la création du projet')
    },
  })
}

// ── useDeleteProject ──────────────────────────────────────────────────────────

export function useDeleteProject() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/projects/${id}`)
      return id
    },
    onSuccess: (deletedId) => {
      void queryClient.invalidateQueries({ queryKey: projectKeys.lists() })
      queryClient.removeQueries({ queryKey: projectKeys.detail(deletedId) })
      toast.success('Projet supprimé')
    },
    onError: () => {
      toast.error('Erreur lors de la suppression du projet')
    },
  })
}
