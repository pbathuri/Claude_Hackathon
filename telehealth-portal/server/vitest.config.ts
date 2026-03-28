import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Run tests in Node environment (not browser)
    environment: "node",
    // Resolve TypeScript paths without .js extension tricks in test files
    globals: true,
    // Test files location
    include: ["src/__tests__/**/*.test.ts"],
    // Timeout for async graph invocations
    testTimeout: 15_000,
    // Coverage
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: ["src/graph/**", "src/services/**"],
      exclude: ["src/__tests__/**"],
    },
  },
  resolve: {
    // Allow importing .ts files without .js extension in tests
    extensions: [".ts", ".js"],
  },
});
