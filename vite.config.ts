import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',          // 🔹 permite acceso desde fuera del host (Docker, LAN, etc.)
    port: 5173,               // 🔹 puerto de desarrollo
    strictPort: true,         // evita que Vite cambie el puerto automáticamente
    allowedHosts: ['host.docker.internal'],
    watch: {
      // Excluir carpetas de runtime que causan recargas innecesarias
      ignored: [
        '**/backend/credentials/**',    // Tokens OAuth (drive-token.json)
        '**/backend/log/**',            // Archivos de log (se escriben constantemente)
        '**/credentials/**',            // Cualquier carpeta credentials
        '**/log/**',                    // Cualquier carpeta log
        '**/.cursor/**',                // Archivos del IDE (pueden contener tokens MCP)
        '**/node_modules/**',          // Ya excluido por defecto, pero por seguridad
        '**/dist/**',                   // Build output
        '**/*.log',                     // Archivos .log en cualquier lugar
      ]
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',  // tu backend local (FastAPI, Express, etc.)
        changeOrigin: true,
        secure: false,
      },
    },
  },
})