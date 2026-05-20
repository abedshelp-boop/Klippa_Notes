import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'node',
    globals: false,
    include: ['src/**/*.test.{js,jsx}', 'electron/**/*.test.js'],
    exclude: ['node_modules', 'dist', 'release', 'python-service'],
  },
});
