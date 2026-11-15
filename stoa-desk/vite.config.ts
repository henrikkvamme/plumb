import babel from "@rolldown/plugin-babel";
import tailwindcss from "@tailwindcss/vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import viteReact, { reactCompilerPreset } from "@vitejs/plugin-react";
import core from "ultracite/oxlint/core";
import react from "ultracite/oxlint/react";
import { defineConfig } from "vite-plus";

const fence = (group: readonly string[], message: string) => ({
  patterns: [{ group: [...group], message }],
});

export default defineConfig({
  fmt: {
    ignorePatterns: ["src/routeTree.gen.ts", "pnpm-lock.yaml", "tools/oxlint/anti-slop/**"],
  },
  lint: {
    extends: [core, react],
    ignorePatterns: [
      "dist/**",
      "node_modules/**",
      "src/routeTree.gen.ts",
      "src/**/*.d.ts",
      "src/components/ui/**",
      "tools/oxlint/**",
      "tools/cli/require-node.mjs",
      ".claude/**",
      ".cursor/**",
    ],
    jsPlugins: [
      "@xstate/effect/oxlint",
      "./tools/oxlint/no-comments.ts",
      "./tools/oxlint/json-import.ts",
      { name: "anti-slop", specifier: "./tools/oxlint/anti-slop/index.ts" },
      { name: "anti-slop-effect", specifier: "./tools/oxlint/anti-slop/effect/index.ts" },
    ],
    options: { typeAware: true },
    overrides: [
      {
        files: ["src/routes/**"],
        rules: {
          "unicorn/filename-case": [
            "error",
            { case: "kebabCase", ignore: ["^\\$[a-z][a-zA-Z0-9]*\\.tsx$"] },
          ],
        },
      },
      {
        files: ["src/domain/**", "src/server/**", "src/api/**", "src/features/**/*.ts", "tools/**"],
        rules: { "react-hooks/rules-of-hooks": "off" },
      },
      {
        files: ["src/domain/**"],
        rules: {
          "no-restricted-imports": [
            "error",
            fence(
              [
                "#/server/**",
                "#/api/**",
                "#/features/**",
                "#/routes/**",
                "#/components/**",
                "react",
                "react-dom",
                "@tanstack/**",
              ],
              "src/domain is pure: schemas, tagged errors, service tags and machines. Fix: move IO to `src/server` and UI to `src/features`.",
            ),
          ],
        },
      },
      {
        files: ["src/server/**"],
        rules: {
          "no-restricted-imports": [
            "error",
            fence(
              [
                "#/api/**",
                "#/features/**",
                "#/routes/**",
                "#/components/**",
                "react",
                "react-dom",
                "@tanstack/**",
              ],
              "src/server holds Effect services only. Fix: put the transport in `src/api` and UI in `src/features`.",
            ),
          ],
        },
      },
      {
        files: ["src/features/**", "src/routes/**", "src/components/**"],
        rules: {
          "no-restricted-imports": [
            "error",
            {
              ...fence(
                ["#/server/**"],
                "The browser cannot import server code. Fix: call a server function from `src/api`.",
              ),
              paths: [
                {
                  importNames: ["Html"],
                  message:
                    "drei `Html` mounts a second React root and logs an unmount race that fails `pnpm j verify browser`. Fix: draw labels in the scene with drei `Text` inside `Billboard`.",
                  name: "@react-three/drei",
                },
              ],
            },
          ],
        },
      },
      {
        files: ["src/api/**"],
        rules: {
          "no-restricted-imports": [
            "error",
            fence(
              ["#/features/**", "#/routes/**", "#/components/**", "react", "react-dom"],
              "src/api is a thin transport. Fix: validate input with a Schema and call one service through `runApi`.",
            ),
          ],
        },
      },
    ],
    rules: {
      "anti-slop-effect/no-manual-effect-error-tag": "error",
      "anti-slop-effect/no-manual-tag-comparison": "error",
      "anti-slop-effect/no-manual-tagged-construction": "error",
      "anti-slop-effect/no-service-constructor-imports": "error",
      "anti-slop-effect/prefer-effect-match": "error",
      "anti-slop/no-array-filter-map": "error",
      "anti-slop/no-chained-type-assertions": "error",
      "anti-slop/no-conditional-empty-object-spread": "error",
      "anti-slop/no-known-value-widening": "error",
      "anti-slop/no-module-mocking": "error",
      "anti-slop/no-object-parameters": "error",
      "anti-slop/no-reduce-accumulator-copy": "error",
      "anti-slop/no-reflect-apply": "error",
      "anti-slop/no-reflect-get": "error",
      "anti-slop/no-runtime-typeof": "error",
      "anti-slop/no-shape-in-symbol-names": "error",
      "anti-slop/no-unknown-parameters": "error",
      "anti-slop/no-unknown-returns": "error",
      "anti-slop/no-unknown-type-aliases": "error",
      "anti-slop/no-unsafe-dictionary-type": "error",
      "anti-slop/no-widen-then-assert": "error",
      "anti-slop/require-readable-spacing": "error",
      "anti-slop/require-safety-comment-for-type-assertion": "error",
      "no-comments/directive-reason": "error",
      "no-comments/no-comments": "error",
      "json-import/require-type-attribute": "error",
      "no-inline-comments": "off",
      "no-redeclare": "off",
      "oxc/no-accumulating-spread": "error",
      "promise/prefer-await-to-callbacks": "off",
      "unicorn/prefer-set-has": "off",
      "typescript/consistent-return": "off",
      "typescript/promise-function-async": "off",
      "unicorn/throw-new-error": "off",
      "xstate-effect/no-inline-effect": "error",
    },
  },
  plugins: [
    tailwindcss(),
    tanstackStart(),
    viteReact(),
    babel({ presets: [reactCompilerPreset()] }),
  ],
  resolve: { tsconfigPaths: true },
  server: { allowedHosts: true },
});
