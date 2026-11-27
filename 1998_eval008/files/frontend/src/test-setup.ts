import '@testing-library/jest-dom/vitest'

// jsdom 缺这两个浏览器 API，TDesign 组件会用到
class RO { observe() {} unobserve() {} disconnect() {} }
;(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = RO
if (!window.matchMedia) {
  ;(window as unknown as { matchMedia: unknown }).matchMedia = (q: string) => ({
    matches: false, media: q, onchange: null,
    addListener() {}, removeListener() {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false,
  })
}
