import { createFileRoute } from "@tanstack/react-router";

import { LayersScreen } from "#/features/landing/layers-screen.tsx";

export const Route = createFileRoute("/")({ component: LayersScreen });
