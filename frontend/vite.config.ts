import { defineConfig } from 'vite';
import solid from 'vite-plugin-solid';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [solid(), tailwindcss()],
  build: {
    outDir: 'dist',
    target: 'esnext',
  },
  server: {
    port: 3000,
    proxy: {
      '/run': 'http://localhost:5002',
    },
  },
});
