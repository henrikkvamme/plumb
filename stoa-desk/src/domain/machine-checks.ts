export interface Invariant<State> {
  readonly holds: (state: State) => boolean;
  readonly name: string;
}

export interface MachineChecks<State> {
  readonly invariants: readonly Invariant<State>[];
  readonly name: string;
  readonly reachable: readonly string[];
  readonly states: () => readonly State[];
  readonly tagOf: (state: State) => string;
}

export interface MachineReport {
  readonly failures: readonly string[];
  readonly name: string;
  readonly statesExplored: number;
}

const traversalLimitFailure =
  "traversal limit exceeded. Fix: pass `serializeState` to `getShortestPaths` and bucket context that grows without bound (days, counters, lists), or raise `limit`.";

const explore = <State>(checks: MachineChecks<State>): readonly State[] | null => {
  try {
    return checks.states();
  } catch (error) {
    if (error instanceof Error && error.message.includes("Traversal limit")) {
      return null;
    }

    throw error;
  }
};

export const machineChecks = <State>(checks: MachineChecks<State>) => ({
  run: (): MachineReport => {
    const explored = explore(checks);

    if (explored === null) {
      return { failures: [traversalLimitFailure], name: checks.name, statesExplored: 0 };
    }

    const states = explored;
    const tags = new Set(states.map(checks.tagOf));

    const unreachable = checks.reachable
      .filter((tag) => !tags.has(tag))
      .map((tag) => `state \`${tag}\` is not reachable with the given events`);

    const broken = checks.invariants.flatMap((invariant) =>
      states
        .filter((state) => !invariant.holds(state))
        .map(
          (state) => `invariant \`${invariant.name}\` fails in state \`${checks.tagOf(state)}\``,
        ),
    );

    return {
      failures: [...unreachable, ...broken],
      name: checks.name,
      statesExplored: states.length,
    };
  },
});

export const afterDelay = (stateId: string, delay: number) =>
  ({ delay, stateId, type: "xstate.after" }) as const;

export const actorDone = <Output>(actorId: string, output: Output) =>
  ({ actorId, output, type: "xstate.done.actor" }) as const;

export const actorFailed = <Failure>(actorId: string, error?: Failure) =>
  ({ actorId, error, type: "xstate.error.actor" }) as const;
