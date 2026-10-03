import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: { port: 5173, strictPort: true, proxy: { '/actuator': 'http://127.0.0.1:8080' } },
  build: { sourcemap: false },
})
