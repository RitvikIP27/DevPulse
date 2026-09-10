import "@testing-library/jest-dom/vitest";

// Recharts' ResponsiveContainer measures its parent via ResizeObserver, which
// jsdom does not implement. The stub lets chart-bearing pages mount; chart
// geometry itself is not what these tests assert.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
