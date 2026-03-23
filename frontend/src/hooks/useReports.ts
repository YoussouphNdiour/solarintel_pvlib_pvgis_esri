import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import type { AxiosError } from 'axios'
import { apiClient } from '@/api/client'
import type {
  ReportCreateResponse,
  ReportRequest,
  ReportStatusResponse,
} from '@/types/api'

// ── Query Keys ────────────────────────────────────────────────────────────────

export const reportKeys = {
  all: () => ['reports'] as const,
  bySimulation: (simulationId: string) =>
    [...reportKeys.all(), 'simulation', simulationId] as const,
  status: (reportId: string) =>
    [...reportKeys.all(), 'status', reportId] as const,
}

// ── useCreateReport ───────────────────────────────────────────────────────────

export function useCreateReport() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: ReportRequest) => {
      const { data } = await apiClient.post<ReportCreateResponse>(
        '/reports',
        payload,
      )
      return data
    },
    onSuccess: (result) => {
      // Seed the status cache with the initial pending state so polling
      // starts immediately without a round-trip gap.
      queryClient.setQueryData<ReportStatusResponse>(
        reportKeys.status(result.reportId),
        {
          id: result.reportId,
          simulationId: '',
          status: result.status,
          pdfPath: null,
          htmlPath: null,
          generatedAt: null,
          createdAt: new Date().toISOString(),
        },
      )
    },
    onError: () => {
      toast.error('Erreur lors du lancement de la génération du rapport')
    },
  })
}

// ── useReportStatus ───────────────────────────────────────────────────────────

export function useReportStatus(reportId: string | null) {
  return useQuery({
    queryKey: reportKeys.status(reportId ?? ''),
    queryFn: async () => {
      const { data } = await apiClient.get<ReportStatusResponse>(
        `/reports/${reportId ?? ''}`,
      )
      return data
    },
    enabled: reportId !== null && reportId.length > 0,
    // Poll every 3s while pending/generating; stop when ready or failed.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'ready' || status === 'failed') return false
      return 3_000
    },
  })
}

// ── useReportsBySimulation ────────────────────────────────────────────────────

export function useReportsBySimulation(simulationId: string) {
  return useQuery({
    queryKey: reportKeys.bySimulation(simulationId),
    queryFn: async () => {
      const { data } = await apiClient.get<ReportStatusResponse[]>(
        '/reports',
        { params: { simulation_id: simulationId } },
      )
      return data
    },
    enabled: simulationId.length > 0,
  })
}

// ── useDownloadReport (PDF blob download) ─────────────────────────────────────

export function useDownloadReport(reportId: string | null) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      reportId: id,
      filename,
    }: {
      reportId: string
      filename: string
    }) => {
      const response = await apiClient.get<Blob>(
        `/reports/${id}/download`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(response.data)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    },
    onSuccess: () => {
      toast.success('Rapport PDF téléchargé ✓')
    },
    onError: (error: unknown) => {
      // If file was lost after a server restart, the status endpoint will
      // auto-reset to pending and re-trigger generation. Invalidate the
      // status cache so the polling loop immediately picks up the change.
      const axiosErr = error as AxiosError<Blob>
      // When responseType='blob', error response data is a Blob — parse it.
      let detail: string | undefined
      try {
        const text = await (axiosErr.response?.data as Blob | undefined)?.text()
        if (text) detail = (JSON.parse(text) as { detail?: string }).detail
      } catch { /* ignore parse errors */ }
      if (detail === 'report_file_missing' && reportId !== null) {
        void queryClient.invalidateQueries({
          queryKey: reportKeys.status(reportId),
        })
        toast('Fichier expiré — régénération en cours…', { icon: '🔄' })
      } else {
        toast.error('Erreur lors du téléchargement du rapport PDF')
      }
    },
  })
}

// ── useDownloadHtmlReport (open in new tab) ───────────────────────────────────

export function useDownloadHtmlReport() {
  return useMutation({
    mutationFn: async (reportId: string) => {
      const { data } = await apiClient.get<{ url: string }>(
        `/reports/${reportId}/html`,
      )
      window.open(data.url, '_blank', 'noopener,noreferrer')
    },
    onError: () => {
      toast.error('Erreur lors de l\'ouverture du rapport HTML')
    },
  })
}
