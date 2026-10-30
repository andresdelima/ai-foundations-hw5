import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dashboard runs on http://localhost:5173 and calls the FastAPI backend at
// http://localhost:8000 (see src/api.ts). The backend's CORS allows this origin.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
})
