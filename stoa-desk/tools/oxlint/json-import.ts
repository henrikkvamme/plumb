import { definePlugin, defineRule } from "@oxlint/plugins";

const jsonImport = defineRule({
  create(context) {
    return {
      ImportDeclaration(node) {
        const source = String(node.source.value);

        if (!source.endsWith(".json")) {
          return;
        }

        const typed = node.attributes.some(
          (attribute) =>
            (attribute.key.type === "Identifier" ? attribute.key.name : attribute.key.value) ===
              "type" && attribute.value.value === "json",
        );

        if (!typed) {
          context.report({
            message: `Import of \`${source}\` has no \`with { type: "json" }\`. Node runs \`pnpm j\` and the machine checks without Vite, and fails with ERR_IMPORT_ATTRIBUTE_MISSING. Fix: write \`import data from "${source}" with { type: "json" };\`.`,
            node,
          });
        }
      },
    };
  },
});

export default definePlugin({
  meta: { name: "json-import" },
  rules: { "require-type-attribute": jsonImport },
});
