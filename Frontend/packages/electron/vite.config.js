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
  },
  resolve: {
    alias: {
      '@context-translator/shared': resolve(__dirname, '../shared/index.js'),
      '@context-translator/shared/styles': resolve(__dirname, '../shared/src/index.css')
    }
  }
})