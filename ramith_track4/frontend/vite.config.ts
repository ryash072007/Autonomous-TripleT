import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

const backend = 'http://127.0.0.1:8000'

// In development the Python API runs on :8000; in production the built files are served by FastAPI itself.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    proxy: Object.fromEntries(['/query', '/evaluate', '/directives', '/doc', '/docket', '/results', '/health'].map((p) => [p, backend])),
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 900 },
})
