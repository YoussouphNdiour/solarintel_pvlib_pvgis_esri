import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./index.css";

// Configure React Query client with sensible defaults for SolarIntel
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Stale time: 5 minutes — simulation data does not change frequently
      staleTime: 5 * 60 * 1000,
      // Cache time: 10 minutes
      gcTime: 10 * 60 * 1000,
      // Retry failed requests twice before surfacing error
      retry: 2,
      // Refetch on window focus (useful for long-running PDF generation)
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 0,
    },
  },
});

const rootElement = document.getElementById("root");

if (rootElement === null) {
  throw new Error(
    "Root element with id='root' not found. Check public/index.html.",
  );
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  </React.StrictMode>,
);
