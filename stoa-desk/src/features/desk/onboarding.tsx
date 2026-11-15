import { useAtomSet, useAtomValue } from "@effect/atom-react";
import { Button } from "@ui-sdk/react/button";
import { Popover, PopoverContent, PopoverDescription, PopoverTitle } from "@ui-sdk/react/popover";
import { AsyncResult } from "effect/reactivity";
import { CircleHelp } from "lucide-react";
import { useEffect, useState } from "react";

import { tourSteps } from "#/domain/desk-tour.machine.ts";
import type { TourStep } from "#/domain/desk-tour.machine.ts";
import type { DrawingDocument, Entity, Run } from "#/domain/desk.ts";

import { centreOf } from "./geometry.ts";
import { tourSend, tourState } from "./onboarding.atoms.ts";

export type TourPhase = "none" | "running" | "answered" | "failed";

export const tourPhaseOf = ({
  busy,
  failed,
  run,
}: {
  readonly busy: boolean;
  readonly failed: boolean;
  readonly run: Run | null;
}): TourPhase => {
  if (failed || run?.status === "error") {
    return "failed";
  }

  if (run?.answer !== null && run?.answer !== undefined) {
    return "answered";
  }

  return busy || run !== null ? "running" : "none";
};

const storageKey = "stoa-desk.tour";

const remembered = (): boolean => {
  try {
    return globalThis.localStorage.getItem(storageKey) !== null;
  } catch {
    return false;
  }
};

const remember = (outcome: string): boolean => {
  try {
    globalThis.localStorage.setItem(storageKey, outcome);

    return true;
  } catch {
    return false;
  }
};

const isStep = (value: string): value is TourStep => tourSteps.some((step) => step === value);

const useTourTag = (): string => {
  const state = useAtomValue(tourState);

  return AsyncResult.isSuccess(state) ? state.value._tag : "idle";
};

export const useTourStep = (): TourStep | null => {
  const tag = useTourTag();

  return isStep(tag) ? tag : null;
};

const areaOf = (entity: Entity): number => {
  const value = Number(entity.facts.find((fact) => fact.key === "Area")?.value ?? Number.NaN);

  return Number.isFinite(value) ? value : 0;
};

export const tourRoomOf = (document: DrawingDocument): Entity | null => {
  if (document.pages.length === 0) {
    return null;
  }

  const rooms = document.entities.filter(
    (entity) => entity.kind === "room" && entity.geometry === "polygon",
  );

  return rooms.toSorted((a, b) => areaOf(b) - areaOf(a))[0] ?? null;
};

export const tourLabels = (
  step: TourStep | null,
  room: Entity | null,
): readonly (readonly [string, string])[] =>
  step === "pick" && room !== null ? [[room.id, room.label]] : [];

const roomSelector = (room: Entity): string => {
  const [x, y] = centreOf(room.points);

  return `[data-chip][data-x="${String(x)}"][data-y="${String(y)}"]`;
};

interface Tip {
  readonly action: string | null;
  readonly align: "start" | "center" | "end";
  readonly body: string;
  readonly number: number;
  readonly offset: number;
  readonly side: "top" | "bottom" | "left" | "right";
  readonly target: string;
  readonly title: string;
}

const tips: Record<TourStep, (room: Entity | null) => Tip> = {
  answering: () => ({
    action: null,
    align: "start",
    body: "Each step it takes shows here while it works.",
    number: 3,
    offset: 12,
    side: "left",
    target: '[data-tour="card"]',
    title: "The agent is reading",
  }),
  ask: () => ({
    action: null,
    align: "end",
    body: "Click one of these questions about the room, or type your own below.",
    number: 2,
    offset: 26,
    side: "left",
    target: '[data-tour="suggest"]',
    title: "Ask about it",
  }),
  own: () => ({
    action: "Done",
    align: "start",
    body: "Click here, or drop a PDF, image, DXF or IFC file anywhere on the page.",
    number: 4,
    offset: 12,
    side: "top",
    target: "button[data-add]",
    title: "Try your own drawing",
  }),
  pick: (room) =>
    room === null
      ? {
          action: null,
          align: "start",
          body: "The agent read this drawing. Click a room in the list to see what it found.",
          number: 1,
          offset: 12,
          side: "left",
          target: '[data-tour="card"]',
          title: "Click a room",
        }
      : {
          action: null,
          align: "center",
          body: "The agent read this drawing. Click a room to see what it found.",
          number: 1,
          offset: 28,
          side: "left",
          target: roomSelector(room),
          title: "Click a room",
        },
  trust: () => ({
    action: "Next",
    align: "start",
    body: "Checks test the answer. Evidence links each number to the drawing.",
    number: 3,
    offset: 26,
    side: "left",
    target: '[data-tour="why"]',
    title: "See why you can trust it",
  }),
};

interface Found {
  readonly element: Element | null;
  readonly selector: string;
}

const useTarget = (selector: string | null): Element | null => {
  const [found, setFound] = useState<Found | null>(null);

  useEffect(() => {
    if (selector === null) {
      return;
    }

    const look = () => {
      const element = globalThis.document.querySelector(selector);

      setFound((current) =>
        current?.selector === selector && current.element === element
          ? current
          : { element, selector },
      );
    };

    look();

    const timer = globalThis.setInterval(look, 250);

    return () => {
      globalThis.clearInterval(timer);
    };
  }, [selector]);

  return found !== null && found.selector === selector ? found.element : null;
};

interface Anchor {
  readonly getBoundingClientRect: () => DOMRect;
}

const anchorOf = (element: Element): Anchor => {
  const last = { rect: element.getBoundingClientRect() };

  return {
    getBoundingClientRect: () => {
      if (element.isConnected) {
        last.rect = element.getBoundingClientRect();
      }

      return last.rect;
    },
  };
};

const narrowSide = (tip: Tip, step: TourStep): Tip["side"] => {
  const wide = globalThis.matchMedia("(min-width: 64rem)").matches;

  if (wide || tip.side === "top" || tip.side === "bottom") {
    return tip.side;
  }

  return step === "pick" ? "bottom" : "top";
};

interface Shown {
  readonly anchor: Anchor;
  readonly element: Element;
  readonly step: TourStep;
  readonly tip: Tip;
}

const useBeacon = (step: TourStep | null) => {
  useEffect(() => {
    if (step === null) {
      return;
    }

    const root = globalThis.document.documentElement;

    root.dataset.tourStep = step;

    return () => {
      delete root.dataset.tourStep;
    };
  }, [step]);
};

export interface OnboardingProps {
  readonly documentId: string;
  readonly phase: TourPhase;
  readonly picked: boolean;
  readonly ready: boolean;
  readonly room: Entity | null;
}

const phaseEvent = {
  answered: "ANSWERED",
  failed: "FAILED",
  none: "CLEARED",
  running: "ASKED",
} as const;

export const Onboarding = ({ documentId, phase, picked, ready, room }: OnboardingProps) => {
  const tag = useTourTag();
  const step = isStep(tag) ? tag : null;
  const send = useAtomSet(tourSend);
  const tip = step === null ? null : tips[step](room);
  const target = useTarget(tip?.target ?? null);
  const [shown, setShown] = useState<Shown | null>(null);

  useEffect(() => {
    if (!remembered()) {
      send({ documentId, type: "START" });
    }

    send({ documentId, type: "OPENED" });
  }, [documentId, send]);

  useEffect(() => {
    if (tag === "done" || tag === "skipped") {
      remember(tag);
    }
  }, [tag]);

  useEffect(() => {
    send({ type: picked ? "PICKED" : "UNPICKED" });
  }, [picked, send]);

  useEffect(() => {
    send({ type: phaseEvent[phase] });
  }, [phase, send]);

  const wanted = ready && step !== null && tip !== null && target !== null ? step : null;

  if (shown === null && wanted !== null && tip !== null && target !== null) {
    setShown({ anchor: anchorOf(target), element: target, step: wanted, tip });
  }

  const open = shown !== null && shown.step === wanted && shown.element === target;

  useBeacon(open ? shown.step : null);

  const skip = () => {
    send({ type: "SKIP" });
  };

  return (
    <Popover
      modal={false}
      onOpenChange={(next, details) => {
        if (next) {
          return;
        }

        if (details.reason === "escape-key") {
          skip();
        } else {
          details.cancel();
        }
      }}
      onOpenChangeComplete={(isOpen) => {
        if (!isOpen) {
          setShown(null);
        }
      }}
      open={open}
    >
      {shown === null ? null : (
        <PopoverContent
          align={shown.tip.align}
          anchor={shown.anchor}
          aria-live="polite"
          className="desk-card desk-tour"
          collisionPadding={16}
          data-testid="tour"
          finalFocus="none"
          initialFocus="none"
          side={narrowSide(shown.tip, shown.step)}
          sideOffset={shown.tip.offset}
        >
          <PopoverTitle>{shown.tip.title}</PopoverTitle>
          <PopoverDescription>{shown.tip.body}</PopoverDescription>
          <footer className="flex items-center justify-between gap-3 pt-1">
            <span className="desk-tour-count" aria-label={`Step ${String(shown.tip.number)} of 4`}>
              {[1, 2, 3, 4].map((number) => (
                <i data-on={number <= shown.tip.number} key={number} />
              ))}
            </span>
            <span className="flex items-center gap-1">
              <Button data-variant="ghost" onClick={skip}>
                Skip tour
              </Button>
              {shown.tip.action === null ? null : (
                <Button
                  data-variant="solid"
                  onClick={() => {
                    send({ type: "NEXT" });
                  }}
                >
                  {shown.tip.action}
                </Button>
              )}
            </span>
          </footer>
        </PopoverContent>
      )}
    </Popover>
  );
};

export const TourButton = ({
  documentId,
  onStart,
}: {
  readonly documentId: string;
  readonly onStart: () => void;
}) => {
  const step = useTourStep();
  const send = useAtomSet(tourSend);

  return (
    <button
      aria-label="Show the tour"
      className="desk-tour-button"
      data-on={step !== null}
      onClick={() => {
        onStart();
        send({ documentId, type: "RESTART" });
      }}
      title="Show the tour"
      type="button"
    >
      <CircleHelp aria-hidden="true" size={15} />
    </button>
  );
};
