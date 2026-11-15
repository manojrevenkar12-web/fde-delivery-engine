class IO {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return []
  }
}
Object.assign(globalThis, { IntersectionObserver: IO, ResizeObserver: IO })
if (!window.matchMedia) {
  Object.assign(window, { matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {} }) })
}

import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
afterEach(cleanup)
