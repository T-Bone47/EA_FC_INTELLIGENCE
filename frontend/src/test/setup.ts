import '@testing-library/jest-dom/vitest'

if (typeof window !== 'undefined') {
  if (!globalThis.localStorage || typeof globalThis.localStorage.clear !== 'function') {
    const store = new Map<string, string>()
    const storage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, String(value)),
      removeItem: (key: string) => store.delete(key),
      clear: () => store.clear(),
      get length() { return store.size },
      key: (i: number) => Array.from(store.keys())[i] ?? null,
    }
    Object.defineProperty(globalThis, 'localStorage', {
      value: storage,
      configurable: true,
      writable: true,
    })
    Object.defineProperty(window, 'localStorage', {
      value: storage,
      configurable: true,
      writable: true,
    })
  }
}
