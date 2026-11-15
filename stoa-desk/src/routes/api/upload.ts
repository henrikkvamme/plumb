import { createFileRoute } from "@tanstack/react-router";

import { uploadDrawing } from "#/api/desk-routes.ts";

export const Route = createFileRoute("/api/upload")({
  server: {
    handlers: {
      POST: ({ request }) => uploadDrawing(request),
    },
  },
});
