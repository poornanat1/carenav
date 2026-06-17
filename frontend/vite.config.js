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
    preview: {
        // Allow the Railway-assigned domain when serving the production build via
        // `vite preview`; without this, Vite returns "Blocked request" for unknown hosts.
        allowedHosts: ['.up.railway.app', '.railway.app'],
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
});
