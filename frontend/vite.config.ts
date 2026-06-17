import { defineConfig } from 'vite';
import path from 'path';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://127.0.0.1:8000',
      '/turn': 'http://127.0.0.1:8000',
      '/members': 'http://127.0.0.1:8000',
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
