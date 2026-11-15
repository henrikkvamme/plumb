import { createFileRoute } from "@tanstack/react-router";

import { sampleFile } from "#/api/desk-routes.ts";

export const Route = createFileRoute("/api/sample")({
  server: {
    handlers: {
      GET: ({ request }) => sampleFile(request),
    },
  },
});
