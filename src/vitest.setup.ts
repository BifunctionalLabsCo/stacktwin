import "@testing-library/jest-dom/vitest";

const storage = (() => {
  const data = new Map<string, string>();
  return {
    get length() {
      return data.size;
    },
    clear() {
      data.clear();
    },
    getItem(key: string) {
      return data.has(key) ? data.get(key) ?? null : null;
    },
    key(index: number) {
      return Array.from(data.keys())[index] ?? null;
    },
    removeItem(key: string) {
      data.delete(key);
    },
    setItem(key: string, value: string) {
      data.set(key, String(value));
    }
  };
})();

Object.defineProperty(window, "localStorage", {
  value: storage,
  configurable: true
});
Object.defineProperty(globalThis, "localStorage", {
  value: storage,
  configurable: true
});
