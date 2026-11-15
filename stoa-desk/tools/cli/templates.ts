const pascal = (name: string) =>
  name
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");

const camel = (name: string) => {
  const value = pascal(name);

  return value.charAt(0).toLowerCase() + value.slice(1);
};

export interface FeatureFile {
  readonly content: string;
  readonly path: string;
}

export const featureFiles = (name: string, packageName: string): readonly FeatureFile[] => {
  const Name = pascal(name);
  const fn = camel(name);
  const serviceKey = Name.toLowerCase() === name ? name : `${name}/${Name}`;

  return [
    {
      content: `import { Schema } from "effect";

export const ${Name}Input = Schema.Struct({
  text: Schema.String.check(Schema.isMinLength(1)),
});

export type ${Name}Input = typeof ${Name}Input.Type;

export const ${Name}Output = Schema.Struct({
  text: Schema.String,
});

export type ${Name}Output = typeof ${Name}Output.Type;

export class ${Name}Failed extends Schema.TaggedError<${Name}Failed>()("${Name}Failed", {
  reason: Schema.String,
}) {}
`,
      path: `src/domain/${name}.ts`,
    },
    {
      content: `import { Context, Effect, Layer } from "effect";

import { ${Name}Failed } from "#/domain/${name}.ts";
import type { ${Name}Input, ${Name}Output } from "#/domain/${name}.ts";

export class ${Name} extends Context.Service<
  ${Name},
  {
    readonly run: (input: ${Name}Input) => Effect.Effect<${Name}Output, ${Name}Failed>;
  }
>()("${packageName}/server/${serviceKey}") {
  static readonly layer = Layer.succeed(${Name}, {
    run: Effect.fn("${Name}.run")(function* run(input: ${Name}Input) {
      if (input.text.trim() === "") {
        return yield* new ${Name}Failed({ reason: "The text is empty." });
      }

      return { text: input.text };
    }),
  });
}
`,
      path: `src/server/${name}.ts`,
    },
    {
      content: `import { createServerFn } from "@tanstack/react-start";
import { Schema } from "effect";

import { ${Name}Failed, ${Name}Input } from "#/domain/${name}.ts";
import { ${Name} } from "#/server/${name}.ts";
import { runApi } from "#/server/runtime.ts";

export const ${fn} = createServerFn({ method: "POST" })
  .validator(Schema.toStandardSchemaV1(${Name}Input))
  .handler(({ data }) => runApi(${Name}Failed)(${Name}.use((service) => service.run(data))));
`,
      path: `src/api/${name}.ts`,
    },
  ];
};
