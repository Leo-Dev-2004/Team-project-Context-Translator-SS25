import { defineConfig } from 'vite'
import { resolve } from 'path'
 
export default defineConfig({
  root: '.',
  base: './',  // Use relative paths for Electron
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        main: 'index.html'
      }
    }
  },
  server: {
    port: 5174
  }
})