import { createFileRoute } from "@tanstack/react-router";

import { pageImage } from "#/api/desk-routes.ts";

export const Route = createFileRoute("/api/page")({
  server: {
    handlers: {
      GET: ({ request }) => pageImage(request),
    },
  },
});
