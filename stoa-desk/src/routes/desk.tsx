import { createFileRoute } from "@tanstack/react-router";

import { DeskScreen } from "#/features/desk/desk-screen.tsx";

export const Route = createFileRoute("/desk")({ component: DeskScreen });
