import { createRouter } from "@tanstack/react-router";

import { routeTree } from "./routeTree.gen.ts";

const NotFound = () => (
  <main className="mx-auto max-w-xl p-8">
    <h1 className="text-2xl font-semibold">Page not found</h1>
  </main>
);

export const getRouter = () =>
  createRouter({
    defaultPreload: "intent",
    defaultNotFoundComponent: NotFound,
    defaultPreloadStaleTime: 0,
    routeTree,
    scrollRestoration: true,
  });

declare module "@tanstack/react-router" {
  interface Register {
    router: ReturnType<typeof getRouter>;
  }
}
