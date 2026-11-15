import { Button } from "@ui-sdk/react/button";
import { Armchair, Minus, Plus, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { readModel } from "./model-payload.ts";
import type { BuildingModel } from "./model-payload.ts";
import { mountModel, viewModes } from "./model-scene.ts";
import type { ModelStage, StageState, ViewMode } from "./model-scene.ts";

type Load =
  | { readonly status: "loading" }
  | { readonly reason: string; readonly status: "failed" }
  | { readonly model: BuildingModel; readonly status: "ready" };

const viewNames: Record<ViewMode, string> = {
  building: "Building",
  cutaway: "Cutaway",
  exploded: "Exploded",
  plan: "Plan",
};

const zoomStep = 1.4;

const noSpaces: readonly string[] = [];

const stop = (event: React.PointerEvent) => {
  event.stopPropagation();
};

const loadModel = async (documentId: string, signal: AbortSignal): Promise<Load> => {
  try {
    const response = await fetch(`/api/model?doc=${encodeURIComponent(documentId)}`, { signal });

    if (!response.ok) {
      return { reason: "The 3D model could not be built from this file.", status: "failed" };
    }

    return { model: readModel(await response.arrayBuffer()), status: "ready" };
  } catch {
    return { reason: "The 3D model did not load.", status: "failed" };
  }
};

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable || ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName));

const keyAction = (key: string, stage: ModelStage, state: StageState) => {
  const order = stage.shownStoreys.indexOf(state.storey);
  const viewIndex = viewModes.indexOf(state.view);

  const actions = new Map([
    [
      "+",
      () => {
        stage.zoom(zoomStep);
      },
    ],
    [
      "-",
      () => {
        stage.zoom(1 / zoomStep);
      },
    ],
    [
      "0",
      () => {
        stage.reset();
      },
    ],
    [
      "[",
      () => {
        stage.setStorey(stage.shownStoreys[Math.max(0, order - 1)] ?? state.storey);
      },
    ],
    [
      "]",
      () => {
        stage.setStorey(
          stage.shownStoreys[Math.min(stage.shownStoreys.length - 1, order + 1)] ?? state.storey,
        );
      },
    ],
    [
      "Escape",
      () => {
        stage.clear();
      },
    ],
    [
      "f",
      () => {
        stage.frame();
      },
    ],
    [
      "v",
      () => {
        stage.setView(viewModes[(viewIndex + 1) % viewModes.length] ?? "cutaway");
      },
    ],
  ]);

  const aliases = new Map([
    ["=", "+"],
    ["F", "f"],
    ["Home", "0"],
    ["PageDown", "["],
    ["PageUp", "]"],
    ["V", "v"],
    ["_", "-"],
  ]);

  const view = viewModes[Number(key) - 1];

  if (view !== undefined) {
    return () => {
      stage.setView(view);
    };
  }

  return actions.get(aliases.get(key) ?? key);
};

const Centred = ({ children }: { readonly children: React.ReactNode }) => (
  <div
    className="absolute inset-0 grid place-items-center p-6"
    style={{ bottom: "var(--desk-free-bottom)", right: "var(--desk-free-right)" }}
  >
    <div className="flex w-full max-w-xs flex-col gap-3 text-center">{children}</div>
  </div>
);

const ModelCanvas = ({
  model,
  selectedSpaces,
}: {
  readonly model: BuildingModel;
  readonly selectedSpaces: readonly string[];
}) => {
  const canvasRef = useRef<HTMLDivElement>(null);
  const labelsRef = useRef<HTMLDivElement>(null);
  const tagRef = useRef<HTMLSpanElement>(null);
  const [stage, setStage] = useState<ModelStage | null>(null);
  const [state, setState] = useState<StageState>({ furniture: false, storey: -1, view: "cutaway" });
  const [label, setLabel] = useState<string | null>(null);
  const spacesKey = selectedSpaces.join("\n");

  useEffect(() => {
    const canvasHost = canvasRef.current;
    const labels = labelsRef.current;
    const tag = tagRef.current;

    if (canvasHost === null || labels === null || tag === null) {
      return;
    }

    const mounted = mountModel({ canvasHost, labels, tag }, model, {
      onHover: setLabel,
      onState: setState,
    });

    setStage(mounted);

    return () => {
      mounted.dispose();
      setStage(null);
    };
  }, [model]);

  useEffect(() => {
    if (stage !== null && spacesKey !== "") {
      stage.mark(spacesKey.split("\n"));
    }
  }, [stage, spacesKey]);

  useEffect(() => {
    if (stage === null) {
      return;
    }

    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || typing(event.target)) {
        return;
      }

      const action = keyAction(event.key, stage, state);

      if (action !== undefined) {
        event.preventDefault();
        action();
      }
    };

    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("keydown", onKey);
    };
  }, [stage, state]);

  return (
    <div className="absolute inset-0 overflow-hidden">
      <div className="absolute inset-0" ref={canvasRef} />
      <div aria-hidden="true" className="pointer-events-none absolute inset-0" ref={labelsRef} />
      <span
        aria-hidden="true"
        className="desk-chip-tag pointer-events-none absolute top-0 left-0"
        ref={tagRef}
        style={{ visibility: label === null ? "hidden" : "visible" }}
      >
        {label}
      </span>

      <div className="absolute top-4 left-4 flex flex-col items-start gap-2">
        <div className="desk-viewpill" onPointerDown={stop}>
          <fieldset className="desk-seg">
            <legend className="sr-only">View</legend>
            {viewModes.map((mode, index) => (
              <button
                aria-pressed={state.view === mode}
                key={mode}
                onClick={() => {
                  stage?.setView(mode);
                }}
                title={`${viewNames[mode]} (${String(index + 1)})`}
                type="button"
              >
                {viewNames[mode]}
              </button>
            ))}
          </fieldset>
          <button
            aria-label="Zoom out"
            className="desk-round"
            onClick={() => {
              stage?.zoom(1 / zoomStep);
            }}
            title="Zoom out (-)"
            type="button"
          >
            <Minus aria-hidden="true" size={16} />
          </button>
          <button
            aria-label="Zoom in"
            className="desk-round"
            onClick={() => {
              stage?.zoom(zoomStep);
            }}
            title="Zoom in (+)"
            type="button"
          >
            <Plus aria-hidden="true" size={16} />
          </button>
          <button
            aria-label="Show furniture"
            aria-pressed={state.furniture}
            className="desk-round"
            onClick={() => {
              stage?.setFurniture(!state.furniture);
            }}
            style={state.furniture ? { background: "#f4f3f0", color: "#111112" } : undefined}
            title="Furniture"
            type="button"
          >
            <Armchair aria-hidden="true" size={16} />
          </button>
          <button
            aria-label="Reset the view"
            className="desk-round"
            onClick={() => {
              stage?.reset();
            }}
            title="Reset (0)"
            type="button"
          >
            <RotateCcw aria-hidden="true" size={16} />
          </button>
        </div>

        {stage !== null && stage.shownStoreys.length > 1 ? (
          <div
            className="desk-viewpill max-w-[calc(100vw-2rem)] overflow-x-auto"
            onPointerDown={stop}
          >
            <fieldset className="desk-seg">
              <legend className="sr-only">Storey</legend>
              {stage.shownStoreys.toReversed().map((index) => (
                <button
                  aria-pressed={state.view !== "building" && state.storey === index}
                  className="whitespace-nowrap"
                  key={index}
                  onClick={() => {
                    stage.setStorey(index);
                  }}
                  title="Storey ([ and ])"
                  type="button"
                >
                  {model.storeys[index]?.name ?? "Storey"}
                </button>
              ))}
            </fieldset>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const ModelView = ({
  documentId,
  selectedSpaces = noSpaces,
}: {
  readonly documentId: string;
  readonly selectedSpaces?: readonly string[];
}) => {
  const [attempt, setAttempt] = useState(0);
  const [loaded, setLoaded] = useState<{ readonly key: string; readonly load: Load } | null>(null);
  const key = `${documentId}#${String(attempt)}`;
  const load: Load = loaded?.key === key ? loaded.load : { status: "loading" };

  useEffect(() => {
    const abort = new AbortController();
    const [id = ""] = key.split("#");

    const run = async () => {
      const next = await loadModel(id, abort.signal);

      if (!abort.signal.aborted) {
        setLoaded({ key, load: next });
      }
    };

    void run();

    return () => {
      abort.abort();
    };
  }, [key]);

  if (load.status === "ready") {
    return <ModelCanvas key={documentId} model={load.model} selectedSpaces={selectedSpaces} />;
  }

  if (load.status === "failed") {
    return (
      <Centred>
        <p role="alert">{load.reason}</p>
        <div className="flex justify-center">
          <Button
            onClick={() => {
              setAttempt((count) => count + 1);
            }}
          >
            Retry
          </Button>
        </div>
      </Centred>
    );
  }

  return (
    <Centred>
      <p aria-busy="true" className="text-lg font-medium">
        Building the 3D model
      </p>
      <div className="desk-progress" />
    </Centred>
  );
};
