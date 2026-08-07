import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
// `defineConfig` vient de vitest/config (et non de vite) pour que le bloc `test` soit typé.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  server: {
    host: true, // nécessaire pour exposer le serveur depuis le conteneur Docker
    port: 5173,
    watch: { usePolling: true }, // le montage de volume Docker ne propage pas les événements inotify
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
});
