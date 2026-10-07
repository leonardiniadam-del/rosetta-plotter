import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "./", // the built page is served from a local folder by pywebview
  build: { outDir: "dist", emptyOutDir: true, target: "es2022" },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    // Vitest blanks every CSS import, `?raw` ones too; let `import css from "x.css?raw"` through so tests can read the text.
    css: { include: [/\.css\?raw$/] },
  },
});
