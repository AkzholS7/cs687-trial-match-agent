import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the React app runs on port 5173 and forwards /api calls to the Flask backend on port 5000.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5173, proxy: { '/api': 'http://localhost:5000' } },
});
