import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/docs': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      '/openapi.json': { target: process.env.API_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true },
      '/api': {
        // Docker resolves 'backend'; locally Vite forwards to localhost.
        target: process.env.API_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
