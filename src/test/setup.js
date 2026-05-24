import '@testing-library/jest-dom/vitest';

// React Flow uses ResizeObserver and getBoundingClientRect; jsdom stubs neither.
// Provide just enough surface for nodes to mount without exploding.
class ResizeObserverShim {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = ResizeObserverShim;
}

// jsdom returns zero-sized rects for everything, which trips React Flow's
// internal bounds checks. Patch the prototype to report a usable viewport.
const proto = HTMLElement.prototype;
const originalGBCR = proto.getBoundingClientRect;
if (originalGBCR.toString().includes('jsdom') || !originalGBCR.toString().includes('width:')) {
  proto.getBoundingClientRect = function () {
    return {
      x: 0, y: 0, top: 0, left: 0, right: 800, bottom: 600,
      width: 800, height: 600, toJSON: () => ({}),
    };
  };
}

// DOMMatrixReadOnly is referenced by @xyflow/react's transform code.
if (typeof globalThis.DOMMatrixReadOnly === 'undefined') {
  class DOMMatrixReadOnlyShim {
    constructor(transform) {
      const match = transform && typeof transform === 'string'
        ? transform.match(/scale\(([^)]+)\)/) : null;
      this.m22 = match ? Number(match[1]) : 1;
    }
  }
  globalThis.DOMMatrixReadOnly = DOMMatrixReadOnlyShim;
}
