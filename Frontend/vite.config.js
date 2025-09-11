import { defineConfig } from 'vite'
import { resolve } from 'path'
 
export default defineConfig({
  root: '.',
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