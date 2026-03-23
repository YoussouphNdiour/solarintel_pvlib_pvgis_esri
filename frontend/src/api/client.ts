/**
 * Axios HTTP client configured for the SolarIntel v2 API.
 *
 * Features:
 * - Base URL from VITE_API_BASE_URL env var
 * - /api/v2 prefix on all requests
 * - Automatic Bearer token injection from localStorage
 * - 401 → trigger token refresh via /api/v2/auth/refresh
 * - Retry original request after successful refresh
 * - Redirect to /login on refresh failure
 */

import axios, {
  AxiosError,
  AxiosInstance,
  InternalAxiosRequestConfig,
} from "axios";

// ── Types ─────────────────────────────────────────────────────────────────────

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

interface ApiError {
  detail: string;
  type?: string;
  status?: number;
}

// ── Token storage helpers (replace with httpOnly cookie in production) ────────

const TOKEN_KEY = "solarintel_access_token";
const REFRESH_TOKEN_KEY = "solarintel_refresh_token";

export const tokenStorage = {
  getAccessToken: (): string | null => localStorage.getItem(TOKEN_KEY),
  setAccessToken: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  getRefreshToken: (): string | null => localStorage.getItem(REFRESH_TOKEN_KEY),
  setRefreshToken: (token: string): void =>
    localStorage.setItem(REFRESH_TOKEN_KEY, token),
  clearAll: (): void => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },
};

// ── Create axios instance ─────────────────────────────────────────────────────

const BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${BASE_URL}/api/v2`,
  timeout: 30_000, // 30 seconds — PDF generation can be slow
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// ── Request interceptor: inject Authorization header ──────────────────────────

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig): InternalAxiosRequestConfig => {
    const token = tokenStorage.getAccessToken();
    if (token !== null && config.headers !== undefined) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => Promise.reject(error),
);

// ── Response interceptor: handle 401 with refresh ────────────────────────────

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: string) => void;
  reject: (reason: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error !== null) {
      reject(error);
    } else if (token !== null) {
      resolve(token);
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    if (error.response?.status === 401 && originalRequest._retry !== true) {
      if (isRefreshing) {
        // Queue this request until refresh completes
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers !== undefined) {
              originalRequest.headers["Authorization"] = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err: unknown) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenStorage.getRefreshToken();

      if (refreshToken === null) {
        // No refresh token available — redirect to login
        tokenStorage.clearAll();
        window.location.href = "/login";
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post<TokenResponse>(
          `${BASE_URL}/api/v2/auth/refresh`,
          { refresh_token: refreshToken },
        );

        tokenStorage.setAccessToken(data.access_token);
        tokenStorage.setRefreshToken(data.refresh_token);

        processQueue(null, data.access_token);

        if (originalRequest.headers !== undefined) {
          originalRequest.headers["Authorization"] =
            `Bearer ${data.access_token}`;
        }

        return apiClient(originalRequest);
      } catch (refreshError: unknown) {
        processQueue(refreshError, null);
        tokenStorage.clearAll();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

// ── Integration endpoints (Sprint 6) ─────────────────────────────────────────

export const getEquipmentPrices = () =>
  apiClient.get<{ panels: import('@/types/api').PanelPrice[]; inverters: import('@/types/api').InverterPrice[] }>('/equipment/prices')

export default apiClient;
