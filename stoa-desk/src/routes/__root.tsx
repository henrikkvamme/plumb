import { HeadContent, Scripts, createRootRoute } from "@tanstack/react-router";
import type { ReactNode } from "react";

import appCss from "../styles.css?url";

const RootDocument = ({ children }: { readonly children: ReactNode }) => (
  <html lang="en">
    <head>
      <style id="ui-sdk-layer-order">@layer theme, base, ui-sdk, components, utilities;</style>
      <HeadContent />
    </head>
    <body>
      {children}
      <Scripts />
    </body>
  </html>
);

export const Route = createRootRoute({
  head: () => ({
    links: [
      { href: appCss, rel: "stylesheet" },
      { href: "/favicon.svg", rel: "icon", type: "image/svg+xml" },
      { href: "/apple-touch-icon.png", rel: "apple-touch-icon" },
    ],
    meta: [
      { charSet: "utf-8" },
      { content: "width=device-width, initial-scale=1", name: "viewport" },
      { title: "Plumb" },
      { content: "Plumb reads a building drawing. An answer you can check.", name: "description" },
      { content: "Plumb", property: "og:title" },
      { content: "An answer you can check.", property: "og:description" },
      { content: "https://plumb.henrikkvamme.no/og.png", property: "og:image" },
      { content: "website", property: "og:type" },
      { content: "summary_large_image", name: "twitter:card" },
      { content: "#111112", name: "theme-color" },
    ],
  }),
  shellComponent: RootDocument,
});
