import { Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'

import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import DashboardPage from '@/pages/DashboardPage'
import NotFound from '@/pages/NotFound'
import SimulatePage from '@/pages/SimulatePage'
import ProjectPage from '@/pages/ProjectPage'
import ReportsPage from '@/pages/ReportsPage'
import EquipmentPage from '@/pages/EquipmentPage'
import MonitoringPage from '@/pages/MonitoringPage'
import PrivateRoute from '@/components/Auth/PrivateRoute'
import AppLayout from '@/components/Layout/AppLayout'

// ── App Router ────────────────────────────────────────────────────────────────

export default function App(): JSX.Element {
  return (
    <>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route element={<PrivateRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route
              path="/projects/:id"
              element={<ProjectPage />}
            />
            <Route
              path="/simulate"
              element={<SimulatePage />}
            />
            <Route
              path="/reports"
              element={<ReportsPage />}
            />
            <Route
              path="/monitoring"
              element={<MonitoringPage />}
            />
            <Route
              path="/equipment"
              element={<EquipmentPage />}
            />
          </Route>
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>

      {/* Global toaster (outside AppLayout so public pages also get toasts) */}
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: { fontFamily: 'Inter, system-ui, sans-serif' },
          success: {
            style: {
              background: '#f0fdf4',
              color: '#166534',
              border: '1px solid #bbf7d0',
            },
          },
          error: {
            style: {
              background: '#fef2f2',
              color: '#991b1b',
              border: '1px solid #fecaca',
            },
          },
        }}
      />
    </>
  )
}
