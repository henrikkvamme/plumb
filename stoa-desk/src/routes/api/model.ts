import { createFileRoute } from "@tanstack/react-router";

import { modelFile } from "#/api/desk-routes.ts";

export const Route = createFileRoute("/api/model")({
  server: {
    handlers: {
      GET: ({ request }) => modelFile(request),
    },
  },
});
