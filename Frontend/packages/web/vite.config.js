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
    port: 5173,
    open: true
  },
  resolve: {
    alias: [
      { find: '@context-translator/shared/styles', replacement: resolve(__dirname, '../shared/src/index.css') },
      { find: '@context-translator/shared', replacement: resolve(__dirname, '../shared/index.js') }
    ]
  }
})