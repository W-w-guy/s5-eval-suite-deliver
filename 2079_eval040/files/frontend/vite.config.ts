import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: 'dist', emptyOutDir: true },
  // 图表库本地打包、不引用外部 CDN：本包不引入任何 CDN，图表用内联 SVG 自绘
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'] },
})
