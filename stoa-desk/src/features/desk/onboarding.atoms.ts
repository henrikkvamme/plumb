import { createActorAtoms } from "@xstate/effect/atom";
import { Layer } from "effect";
import { Atom } from "effect/reactivity";

import { deskTourMachine } from "#/domain/desk-tour.machine.ts";

const tour = createActorAtoms(Atom.runtime(Layer.empty), deskTourMachine);

export const tourState = Atom.keepAlive(tour.state);

export const tourSend = tour.send;
