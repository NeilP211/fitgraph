import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  // Resolve only the "@/..." alias (not scoped npm packages like "@scope/x").
  resolve: {
    alias: [{ find: /^@\//, replacement: `${dir}/` }],
  },
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
  },
});
