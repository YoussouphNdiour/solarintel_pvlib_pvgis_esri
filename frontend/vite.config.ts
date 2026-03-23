import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [
      react(),
      VitePWA({
        // generateSW lets Workbox handle precaching automatically
        strategies: 'generateSW',
        registerType: 'autoUpdate',
        workbox: {
          // Cache static assets with cache-first
          globPatterns: ['**/*.{js,css,html,ico,png,svg,webp,woff2}'],
          // Network-first for API calls
          runtimeCaching: [
            {
              urlPattern: /^\/api\//,
              handler: 'NetworkFirst',
              options: {
                cacheName: 'api-cache',
                networkTimeoutSeconds: 5,
                cacheableResponse: { statuses: [0, 200] },
              },
            },
          ],
          // Offline fallback
          navigateFallback: '/index.html',
          navigateFallbackDenylist: [/^\/api\//],
          skipWaiting: true,
          clientsClaim: true,
        },
        manifest: {
          name: 'SolarIntel v2',
          short_name: 'SolarIntel',
          description: 'Dimensionnement PV pour l\'Afrique de l\'Ouest',
          theme_color: '#f59e0b',
          background_color: '#ffffff',
          display: 'standalone',
          orientation: 'portrait-primary',
          start_url: '/',
          icons: [
            {
              src: '/icons/icon-192.png',
              sizes: '192x192',
              type: 'image/png',
              purpose: 'any maskable',
            },
            {
              src: '/icons/icon-512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any maskable',
            },
          ],
        },
      }),
    ],

    // Path aliases for cleaner imports
    resolve: {
      alias: {
        '@': '/src',
        '@api': '/src/api',
        '@components': '/src/components',
        '@pages': '/src/pages',
        '@hooks': '/src/hooks',
        '@types': '/src/types',
        '@utils': '/src/utils',
        '@stores': '/src/stores',
      },
    },

    // Dev server configuration
    server: {
      port: 5173,
      host: true, // Expose on all interfaces for Docker networking
      proxy: {
        // Proxy /api requests to the backend during development
        '/api': {
          target: env['VITE_API_BASE_URL'] ?? 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },

    // Build optimisation
    build: {
      target: 'es2020',
      outDir: 'dist',
      // Sourcemaps disabled by default to avoid OOM with large packages like
      // @arcgis/core. Enable with VITE_SOURCEMAP=true for debugging builds.
      sourcemap: process.env['VITE_SOURCEMAP'] === 'true',
      rollupOptions: {
        output: {
          // Chunk splitting for better caching
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            query: ['@tanstack/react-query'],
            forms: ['react-hook-form', '@hookform/resolvers', 'zod'],
            state: ['zustand'],
            charts: ['chart.js', 'react-chartjs-2'],
            // @arcgis/core is dynamically imported — do NOT include here
          },
        },
      },
    },

    // Optimise ArcGIS ES modules (large package, needs special handling)
    optimizeDeps: {
      exclude: ['@arcgis/core'],
    },

    // CSS processing
    css: {
      postcss: './postcss.config.js',
    },
  }
})
