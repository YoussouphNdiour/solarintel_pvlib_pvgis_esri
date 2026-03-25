// ── API types mirroring backend Pydantic schemas exactly ─────────────────────

export type UserRole = 'admin' | 'commercial' | 'technicien' | 'client'

export interface UserResponse {
  id: string
  email: string
  fullName: string | null
  role: UserRole
  company: string | null
  isActive: boolean
  createdAt: string
}

export interface Project {
  id: string
  userId: string
  name: string
  description: string | null
  latitude: number
  longitude: number
  polygonGeojson: Record<string, unknown> | null
  address: string | null
  createdAt: string
}

export interface MonthlyData {
  month: number
  energyKwh: number
  irradianceKwhM2: number
  performanceRatio: number
}

export interface Simulation {
  id: string
  projectId: string
  panelCount: number
  peakKwc: number
  annualKwh: number
  specificYield: number
  performanceRatio: number
  monthlyData: MonthlyData[]
  senelecSavingsXof: number | null
  paybackYears: number | null
  roiPercent: number | null
  status: 'pending' | 'running' | 'completed' | 'failed'
  createdAt: string
}

export interface TokenResponse {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export interface RegisterRequest {
  email: string
  password: string
  fullName?: string
  company?: string
  role?: UserRole
}

export interface LoginRequest {
  email: string
  password: string
}

// ── Paginated responses ───────────────────────────────────────────────────────

export interface CursorPage<T> {
  items: T[]
  nextCursor: string | null
  total: number
}

// ── Create project request ────────────────────────────────────────────────────

export interface CreateProjectRequest {
  name: string
  description?: string
  latitude: number
  longitude: number
  address?: string
  polygonGeojson?: Record<string, unknown>
}

// ── Simulation request / extended results ─────────────────────────────────────

export interface SimulationRequest {
  projectId: string
  /** Omit to let the backend auto-calculate from monthlyConsumptionKwh + availableAreaM2 */
  panelCount?: number
  /** Usable installation area in m² — caps the auto-calculated panel count */
  availableAreaM2?: number
  panelPowerWc: number        // default 545
  panelModel: string
  tilt: number                // degrees, default 15
  azimuth: number             // default 180 (south)
  systemLosses: number        // default 0.14
  monthlyConsumptionKwh: number
  tariffCode: 'DPP' | 'DMP' | 'PPP' | 'PMP' | 'WOYOFAL'
  installationCostXof: number
}

export interface SenelecMonthlySavings {
  month: number
  productionKwh: number
  consumptionKwh: number
  beforeXof: number
  afterXof: number
  savingsXof: number
}

export interface SimulationFull extends Simulation {
  monthlyBreakdown: SenelecMonthlySavings[]
  tariffCode: string
  installationCostXof: number
  panelModel: string
}

// ── AI Analysis types ─────────────────────────────────────────────────────────

export interface QACriterion {
  code: string           // "V1" through "V8"
  label: string
  status: 'PASS' | 'FAIL' | 'NA'
  value: string | null
  threshold: string
  comment: string
}

export interface EquipmentRecommendation {
  inverterModel: string
  inverterKva: number
  inverterBrand: string
  batteryModel: string | null
  batteryKwh: number | null
  systemType: 'on-grid' | 'hybrid' | 'off-grid'
  reasoning: string
}

export interface AnalysisResult {
  simulationId: string
  equipmentRecommendation: EquipmentRecommendation
  reportNarrative: string
  qaResults: {
    criteria: QACriterion[]
    overall: 'PASS' | 'FAIL'
    score: number   // 0-8
  }
  durationMs: number
  errors: string[]
}

// SSE event payloads
export type SSEStatusEvent = { agent: string; status: 'running' | 'done' | 'error' }
export type SSENarrativeToken = { token: string }
export type SSEAgentResult = { agent: string; data: unknown }
export type SSEComplete = { analysis: AnalysisResult }

// Discriminated union for all SSE event shapes
export type SSEEvent =
  | ({ type: 'status' } & SSEStatusEvent)
  | ({ type: 'narrative_token' } & SSENarrativeToken)
  | ({ type: 'agent_result' } & SSEAgentResult)
  | ({ type: 'complete' } & SSEComplete)
  | { type: 'error'; message: string }

// ── Report types ──────────────────────────────────────────────────────────────

export type ReportStatus = 'pending' | 'generating' | 'ready' | 'failed'

export interface ReportCreateResponse {
  reportId: string
  status: ReportStatus
  message: string
}

export interface ReportStatusResponse {
  id: string
  simulationId: string
  status: ReportStatus
  pdfPath: string | null
  htmlPath: string | null
  generatedAt: string | null
  createdAt: string
}

export interface ReportRequest {
  simulationId: string
  clientName?: string
  installerName?: string
  dashboardUrl?: string
}

// ── Monitoring types (MON-001) ────────────────────────────────────────────────

export interface ProductionStats {
  todayKwh: number
  monthKwh: number
  yearKwh: number
  todayExpectedKwh: number
  monthExpectedKwh: number
  yearExpectedKwh: number
  todayPerformancePct: number
  monthPerformancePct: number
  yearPerformancePct: number
  lastReadingAt: string | null
  dataPointsToday: number
}

export interface MonitoringReading {
  id: string
  projectId: string
  timestamp: string
  productionKwh: number
  irradianceWm2: number | null
  temperatureC: number | null
  source: string
}

export interface MonitoringHistoryResponse {
  items: MonitoringReading[]
  nextCursor: string | null
  total: number
}

export interface MonthlyComparison {
  month: number
  year: number
  actualKwh: number
  simulatedKwh: number
  performancePct: number
  irradianceKwhM2: number | null
}

// WebSocket event union (discriminated by 'type')
export type WSMonitoringEvent =
  | { type: 'stats'; data: ProductionStats }
  | { type: 'reading'; data: MonitoringReading }
  | { type: 'alert'; data: { message: string } }
  | { type: 'ping' }

// ── Integration types (Sprint 6) ──────────────────────────────────────────────

export interface WeatherCorrection {
  correctionFactor: number
  measuredDailyKwhM2: number
  simulatedDailyKwhM2: number
  temperatureDeltaC: number
  date: string
}

export interface PanelPrice {
  model: string
  brand: string
  powerWc: number
  priceXof: number
  priceEur: number
  supplier: string
}

export interface InverterPrice {
  model: string
  brand: string
  kva: number
  priceXof: number
  supplier: string
}

export interface SendReportWhatsAppRequest {
  reportId: string
  phone: string
  caption?: string
}
