import { deskFlowChecks } from "./desk-flow.machine.ts";
import { deskTourChecks } from "./desk-tour.machine.ts";

export const allMachineChecks = [deskFlowChecks, deskTourChecks];
