import { useAtomSet, useAtomValue } from "@effect/atom-react";
import { Button } from "@ui-sdk/react/button";
import { Input } from "@ui-sdk/react/input";
import { Tabs, TabsList, TabsPanel, TabsTab } from "@ui-sdk/react/tabs";
import { Match, Predicate } from "effect";
import { AsyncResult } from "effect/reactivity";
import { ArrowLeft, ArrowUp, MousePointerClick, Ruler, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

import { removeDrawing } from "#/api/desk.ts";
import { firstSample } from "#/domain/desk-flow.machine.ts";
import type {
  Derivation,
  DrawingDocument,
  Entity,
  Run,
  Scaled,
  Step,
  Translation,
} from "#/domain/desk.ts";

import { Checks, Hero, Sources } from "./answer-card.tsx";
import { BrandMark } from "./brand-mark.tsx";
import { deskFlow } from "./desk.atoms.ts";
import {
  DrawingStrip,
  DropZone,
  acceptedLabel,
  isAccepted,
  isVisible,
  rememberUpload,
} from "./drawings.tsx";
import { EntityCard, SelectionCard, selectionQuestions } from "./entity-card.tsx";
import { FactsPanel } from "./facts-panel.tsx";
import { numberLabel } from "./format.ts";
import {
  Onboarding,
  TourButton,
  tourLabels,
  tourPhaseOf,
  tourRoomOf,
  useTourStep,
} from "./onboarding.tsx";
import { ScaleCard } from "./scale-tool.tsx";
import type { MeasurePoint } from "./scale-tool.tsx";
import { boundsOf, unionOf } from "./geometry.ts";
import { Trace } from "./trace.tsx";
import { LanguagePick } from "./translate.tsx";
import { LoadingScene, readingSteps, useReadingStep } from "./loading-scene.tsx";
import { ModelView } from "./model-view.tsx";
import { Viewer } from "./viewer.tsx";
import type { Focus, Measure } from "./viewer.tsx";

interface Hover {
  readonly ids: readonly string[];
  readonly stepId: string | null;
}

const noIds: readonly string[] = [];

const labelsOf = (derivation: Derivation | null): ReadonlyMap<string, string> =>
  new Map(
    (derivation?.operands ?? []).flatMap((operand) => {
      const [only, more] = operand.entityIds;

      return only !== undefined && more === undefined && Predicate.isNumber(operand.value)
        ? [[only, numberLabel(Math.round(operand.value * 100) / 100)] as const]
        : [];
    }),
  );

const Skeleton = () => (
  <div aria-busy="true" className="flex flex-col gap-3">
    <span className="desk-bar h-16 w-48" />
    <span className="desk-bar h-[18px] w-full" />
    <span className="desk-bar h-4 w-56" />
  </div>
);

const ProblemNote = ({
  onRetry,
  text,
}: {
  readonly onRetry: () => void;
  readonly text: string;
}) => (
  <div className="flex items-center justify-between gap-3" role="alert">
    <p>{text}</p>
    <Button onClick={onRetry}>Retry</Button>
  </div>
);

interface Links {
  readonly hotIds: ReadonlySet<string>;
  readonly hotStepId: string | null;
  readonly onHoverEntities: (ids: readonly string[] | null) => void;
  readonly onHoverStep: (step: Step | null) => void;
  readonly onHoverStepId: (id: string | null) => void;
  readonly onSelectEntity: (id: string) => void;
  readonly onShowStep: (step: Step) => void;
}

const Suggestions = ({
  onAsk,
  questions,
  title,
}: {
  readonly onAsk: (question: string) => void;
  readonly questions: readonly string[];
  readonly title: string;
}) => (
  <section aria-label="Example questions" className="flex flex-col gap-1" data-tour="suggest">
    <h2 className="desk-heading truncate px-2">{title}</h2>
    {questions.map((question) => (
      <button
        className="desk-suggest"
        key={question}
        onClick={() => {
          onAsk(question);
        }}
        type="button"
      >
        {question}
      </button>
    ))}
  </section>
);

const suggestTitle = (selected: readonly Entity[]): string => {
  const [first] = selected;

  if (first === undefined) {
    return "Try a question";
  }

  return selected.length === 1
    ? `Ask about ${first.label}`
    : `Ask about these ${String(selected.length)} items`;
};

const scaleFact = (document: DrawingDocument) =>
  document.summary.find((row) => row.key.startsWith("Scale") || row.key === "Pixels per metre");

const ScaleTag = ({
  document,
  onScale,
}: {
  readonly document: DrawingDocument;
  readonly onScale: (() => void) | undefined;
}) => {
  const fact = scaleFact(document);
  const known = fact !== undefined && fact.value !== null;
  const found = fact?.key === "Scale" && known ? `Scale ${fact.value ?? ""}` : "Scale found";
  const text = fact?.source === "user" ? "Your scale" : found;

  if (onScale !== undefined) {
    return (
      <button
        className="desk-tag cursor-pointer"
        data-state={known ? "known" : "unknown"}
        data-testid="set-scale"
        onClick={onScale}
        title="Give the scale yourself: click two points and type their real distance"
        type="button"
      >
        <Ruler aria-hidden="true" size={12} />
        {known ? `${text} · change` : "Set the scale"}
      </button>
    );
  }

  if (fact === undefined) {
    return null;
  }

  return (
    <span
      className="desk-tag"
      data-state={known ? "known" : "unknown"}
      title={known ? `${fact.key}: ${fact.value ?? ""}. ${fact.source}` : fact.source}
    >
      <Ruler aria-hidden="true" size={12} />
      {known ? text : "No scale found"}
    </span>
  );
};

const CardHead = ({
  document,
  onScale,
  onTour,
  onTranslated,
}: {
  readonly document: DrawingDocument | null;
  readonly onScale?: (() => void) | undefined;
  readonly onTour?: () => void;
  readonly onTranslated?: (translation: Translation | null) => void;
}) => (
  <header className="flex flex-col gap-2.5 px-[18px] pt-[18px]">
    <div className="flex items-center justify-between gap-3">
      <span className="flex items-center gap-1">
        <h1 className="desk-brand flex items-center gap-1.5 whitespace-nowrap">
          <BrandMark />
          Plumb
        </h1>
        {document === null || onTour === undefined ? null : (
          <TourButton documentId={document.id} onStart={onTour} />
        )}
      </span>
      {document === null ? null : (
        <span className="desk-tag min-w-0">
          <span className="truncate">{document.name}</span>
        </span>
      )}
    </div>
    {document === null ? null : (
      <div className="flex items-center gap-1.5">
        <ScaleTag document={document} onScale={onScale} />
        {onTranslated === undefined || document.entities.length === 0 ? null : (
          <LanguagePick documentId={document.id} onTranslated={onTranslated} />
        )}
      </div>
    )}
  </header>
);

interface CardBodyProps extends Links {
  readonly busy: boolean;
  readonly document: DrawingDocument;
  readonly failed: boolean;
  readonly onAsk: (question: string) => void;
  readonly onBack: () => void;
  readonly onRetry: () => void;
  readonly onShowEntities: (ids: readonly string[]) => void;
  readonly run: Run | null;
  readonly selected: readonly Entity[];
}

const Back = ({ onBack }: { readonly onBack: () => void }) => (
  <button className="desk-back" onClick={onBack} type="button">
    <ArrowLeft aria-hidden="true" size={14} />
    Overview
  </button>
);

const Settled = ({
  document,
  hotIds,
  hotStepId,
  onHoverEntities,
  onHoverStep,
  onHoverStepId,
  onSelectEntity,
  onShowEntities,
  onShowStep,
  run,
}: Links & {
  readonly document: DrawingDocument;
  readonly onShowEntities: (ids: readonly string[]) => void;
  readonly run: Run;
}) => {
  const { answer } = run;

  if (answer === null) {
    return (
      <>
        <p className="desk-question">{run.question}</p>
        {run.status === "error" ? <p role="alert">{run.error}</p> : <Skeleton />}
        <Trace
          hotIds={hotIds}
          hotStepId={hotStepId}
          onHoverEntities={onHoverEntities}
          onHoverStep={onHoverStep}
          onSelectEntity={onSelectEntity}
          onShowStep={onShowStep}
          run={run}
        />
      </>
    );
  }

  return (
    <>
      <Hero about={run.about} answer={answer} question={run.question} />
      <Tabs
        className="desk-tabs"
        defaultValue={answer.status === "answered" ? "checks" : "evidence"}
      >
        <TabsList aria-label="Why this answer" data-tour="why">
          <TabsTab value="checks">Checks</TabsTab>
          <TabsTab value="evidence">Evidence</TabsTab>
          <TabsTab value="facts">Facts</TabsTab>
        </TabsList>
        <TabsPanel value="checks">
          <Checks answer={answer} hotStepId={hotStepId} onHoverStepId={onHoverStepId} />
        </TabsPanel>
        <TabsPanel className="flex flex-col gap-5" value="evidence">
          {answer.derivation === null ? null : (
            <Sources
              derivation={answer.derivation}
              hotIds={hotIds}
              onHoverEntities={onHoverEntities}
              onSelectEntity={onSelectEntity}
            />
          )}
          <Trace
            hotIds={hotIds}
            hotStepId={hotStepId}
            onHoverEntities={onHoverEntities}
            onHoverStep={onHoverStep}
            onSelectEntity={onSelectEntity}
            onShowStep={onShowStep}
            run={run}
          />
        </TabsPanel>
        <TabsPanel value="facts">
          <FactsPanel
            document={document}
            hotIds={hotIds}
            onHoverEntities={onHoverEntities}
            onSelectEntity={onSelectEntity}
            onShowEntities={onShowEntities}
          />
        </TabsPanel>
      </Tabs>
    </>
  );
};

const CardBody = ({
  busy,
  document,
  failed,
  hotIds,
  hotStepId,
  onAsk,
  onBack,
  onHoverEntities,
  onHoverStep,
  onHoverStepId,
  onRetry,
  onSelectEntity,
  onShowEntities,
  onShowStep,
  run,
  selected,
}: CardBodyProps) => {
  if (failed) {
    return (
      <>
        <Back onBack={onBack} />
        <ProblemNote onRetry={onRetry} text="The agent did not answer." />
      </>
    );
  }

  if (run !== null) {
    return (
      <>
        <Back onBack={onBack} />
        <Settled
          document={document}
          hotIds={hotIds}
          hotStepId={hotStepId}
          onHoverEntities={onHoverEntities}
          onHoverStep={onHoverStep}
          onHoverStepId={onHoverStepId}
          onSelectEntity={onSelectEntity}
          onShowEntities={onShowEntities}
          onShowStep={onShowStep}
          run={run}
        />
      </>
    );
  }

  if (busy) {
    return (
      <>
        <Back onBack={onBack} />
        <Skeleton />
      </>
    );
  }

  return (
    <>
      <Suggestions
        onAsk={onAsk}
        questions={selected.length === 0 ? document.questions : selectionQuestions(selected)}
        title={suggestTitle(selected)}
      />
      <FactsPanel
        document={document}
        hotIds={hotIds}
        onHoverEntities={onHoverEntities}
        onSelectEntity={onSelectEntity}
        onShowEntities={onShowEntities}
      />
    </>
  );
};

const Shell = ({
  card,
  children,
  stage,
}: {
  readonly card: ReactNode;
  readonly children?: ReactNode;
  readonly stage: ReactNode;
}) => (
  <main className="desk-frame relative flex min-h-dvh flex-col lg:block lg:h-dvh lg:overflow-hidden">
    <div className="relative h-[58dvh] min-h-0 shrink-0 lg:absolute lg:inset-0 lg:h-auto">
      {stage}
    </div>
    <aside
      className="desk-card flex min-h-0 flex-1 flex-col lg:absolute lg:top-4 lg:right-4 lg:bottom-4 lg:w-[400px]"
      data-tour="card"
    >
      {card}
    </aside>
    {children}
  </main>
);

const linkedDrawing = (): string | null => {
  const id = new URLSearchParams(globalThis.location.search).get("d") ?? "";

  return /^[a-z0-9-]{1,60}$/u.test(id) ? id : null;
};

const linkDrawing = (sample: string) => {
  const url = new URL(globalThis.location.href);

  if (url.searchParams.get("d") !== sample) {
    url.searchParams.set("d", sample);
    globalThis.history.replaceState(globalThis.history.state, "", url);
  }
};

const picked = (current: readonly string[], id: string, add: boolean): readonly string[] => {
  if (!add) {
    return [id];
  }

  return current.includes(id) ? current.filter((other) => other !== id) : [...current, id];
};

const Picked = ({
  entities,
  onAsk,
  onClear,
  onRemove,
}: {
  readonly entities: readonly Entity[];
  readonly onAsk: (question: string) => void;
  readonly onClear: () => void;
  readonly onRemove: (id: string) => void;
}) => {
  const [first] = entities;

  if (first === undefined) {
    return null;
  }

  return entities.length === 1 ? (
    <EntityCard entity={first} onAsk={onAsk} onClose={onClear} />
  ) : (
    <SelectionCard entities={entities} onAsk={onAsk} onClose={onClear} onRemove={onRemove} />
  );
};

const ModelStage = ({
  document,
  spaces,
}: {
  readonly document: DrawingDocument;
  readonly spaces: readonly string[];
}) =>
  document.name.toLowerCase().endsWith(".ifc") || document.kind.startsWith("ifc") ? (
    <div className="absolute inset-0">
      <ModelView documentId={document.id} selectedSpaces={spaces} />
    </div>
  ) : (
    <StageNote>
      <p className="text-lg font-medium">{document.kindLabel}</p>
      <p className="desk-fine">
        This file has no flat page to show. The agent reads the file itself. Ask a question in the
        card.
      </p>
    </StageNote>
  );

const StageNote = ({
  busy,
  children,
}: {
  readonly busy?: boolean;
  readonly children: ReactNode;
}) => (
  <div aria-busy={busy} className="desk-canvas grid h-full cursor-default place-items-center p-6">
    <div className="flex max-w-sm flex-col gap-3 text-center lg:mr-[432px]">{children}</div>
  </div>
);

interface DeskProps {
  readonly busy: boolean;
  readonly document: DrawingDocument;
  readonly failed: boolean;
  readonly onAsk: (text: string, about: readonly string[]) => void;
  readonly onBack: () => void;
  readonly onFile: (file: File) => void;
  readonly onOpen: (sample: string) => void;
  readonly onRetry: () => void;
  readonly onScaled: (patch: Scaled) => void;
  readonly run: Run | null;
  readonly sampleId: string;
}

const translated = (document: DrawingDocument, translation: Translation | null): DrawingDocument =>
  translation === null
    ? document
    : {
        ...document,
        entities: document.entities.map((entity) => ({
          ...entity,
          label: translation.texts[entity.label] ?? entity.label,
        })),
      };

const translationLabels = (
  source: DrawingDocument,
  translation: Translation | null,
): ReadonlyMap<string, string> =>
  new Map(
    translation === null
      ? []
      : source.entities.flatMap((entity) => {
          const text = translation.texts[entity.label];

          return text === undefined || entity.kind === "door" ? [] : [[entity.id, text] as const];
        }),
  );

const askHint = (count: number): string =>
  count === 0 ? "Ask about this drawing" : "Ask about the selection";

const AboutChip = ({
  labels,
  onClear,
}: {
  readonly labels: readonly string[];
  readonly onClear: () => void;
}) =>
  labels.length === 0 ? null : (
    <p className="desk-about mx-[14px] mb-1.5" data-testid="ask-about">
      <MousePointerClick aria-hidden="true" className="shrink-0" size={13} />
      <span className="truncate">
        {labels.length === 1 ? labels[0] : `${String(labels.length)} selected items`}
      </span>
      <button
        aria-label="Ask about the whole drawing"
        onClick={onClear}
        title="Ask about the whole drawing"
        type="button"
      >
        <X aria-hidden="true" size={12} />
      </button>
    </p>
  );

const measureOf = (
  points: readonly MeasurePoint[] | null,
  set: (
    update: (current: readonly MeasurePoint[] | null) => readonly MeasurePoint[] | null,
  ) => void,
): Measure | null =>
  points === null
    ? null
    : {
        onPoint: (point) => {
          set((current) =>
            current === null || current.length >= 2 ? current : [...current, point],
          );
        },
        points,
      };

const Desk = ({
  busy,
  document: source,
  failed,
  onAsk,
  onBack,
  onFile,
  onOpen,
  onRetry,
  onScaled,
  run,
  sampleId,
}: DeskProps) => {
  const [text, setText] = useState("");
  const [hover, setHover] = useState<Hover | null>(null);
  const [selectedIds, setSelectedIds] = useState<readonly string[]>([]);
  const [gone, setGone] = useState<readonly string[]>([]);
  const [painted, setPainted] = useState(source.pages.length === 0);
  const [measuring, setMeasuring] = useState<readonly MeasurePoint[] | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [focusedRun, setFocusedRun] = useState("");
  const [translation, setTranslation] = useState<Translation | null>(null);
  const document = translated(source, translation);
  const [page] = document.pages;
  const scales = page !== undefined && document.kind.startsWith("raster");

  const startScale = () => {
    setSelectedIds([]);
    setMeasuring([]);
  };

  const byId = new Map(document.entities.map((entity) => [entity.id, entity]));

  const expand = (ids: readonly string[]): ReadonlySet<string> =>
    new Set(ids.flatMap((id) => [id, ...(byId.get(id)?.members ?? [])]));

  const flyTo = (ids: ReadonlySet<string>) => {
    const box = unionOf(
      [...ids]
        .flatMap((id): readonly Entity[] => {
          const entity = byId.get(id);

          return entity === undefined ? [] : [entity];
        })
        .map((entity) => boundsOf(entity.points)),
    );

    if (box !== null) {
      setFocus((current) => ({ box, nonce: (current?.nonce ?? 0) + 1 }));
    }
  };

  const derivation = run?.answer?.derivation ?? null;
  const answerIds = expand(derivation?.entityIds ?? noIds);

  if (run !== null && run.answer !== null && run.id !== focusedRun) {
    setFocusedRun(run.id);
    flyTo(answerIds);
  }

  const hotStep = run?.steps.find((step) => step.id === hover?.stepId);
  const hotIds = expand(hover?.ids ?? noIds);

  const ask = (question: string) => {
    const trimmed = question.trim();

    if (trimmed !== "" && !busy) {
      setText("");
      setHover(null);
      onAsk(trimmed, selectedIds);
    }
  };

  const hoverEntities = (ids: readonly string[] | null) => {
    setHover(ids === null ? null : { ids, stepId: null });
  };

  const select = (id: string) => {
    setSelectedIds([id]);
    flyTo(expand([id]));
  };

  const own = useMemo(() => rememberUpload(sampleId), [sampleId]);

  const samples = document.samples.filter(
    (sample) => !gone.includes(sample.id) && isVisible(sample.id, own, sampleId),
  );

  const remove = async (id: string) => {
    const result = await removeDrawing({ data: { sample: id } }).catch(() => null);

    if (result?.ok !== true) {
      return;
    }

    setGone((current) => [...current, id]);

    if (id === sampleId) {
      onOpen(firstSample);
    }
  };

  const pick = (id: string, add: boolean) => {
    setSelectedIds((current) => picked(current, id, add));
  };

  const selected = selectedIds.flatMap((id) => byId.get(id) ?? []);
  const tourStep = useTourStep();
  const tourRoom = tourRoomOf(source);

  return (
    <Shell
      card={
        <>
          <CardHead
            document={document}
            onScale={scales ? startScale : undefined}
            onTour={() => {
              setSelectedIds([]);
              setHover(null);
              onBack();
            }}
            onTranslated={setTranslation}
          />
          <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-[18px] py-5">
            <CardBody
              busy={busy}
              document={document}
              failed={failed}
              hotIds={hotIds}
              hotStepId={hover?.stepId ?? null}
              onAsk={ask}
              onBack={() => {
                setHover(null);
                onBack();
              }}
              onHoverEntities={hoverEntities}
              onHoverStep={(step) => {
                setHover(step === null ? null : { ids: step.entityIds, stepId: step.id });
              }}
              onHoverStepId={(id) => {
                setHover(id === null ? null : { ids: noIds, stepId: id });
              }}
              onRetry={onRetry}
              onSelectEntity={select}
              onShowEntities={(ids) => {
                flyTo(expand(ids));
              }}
              onShowStep={(step) => {
                flyTo(expand(step.entityIds));
              }}
              run={run}
              selected={selected}
            />
          </div>
          <AboutChip
            labels={selected.map((entity) => entity.label)}
            onClear={() => {
              setSelectedIds([]);
            }}
          />
          <form
            className="desk-ask m-[14px] mt-0"
            data-tour="ask"
            onSubmit={(event) => {
              event.preventDefault();
              ask(text);
            }}
          >
            <Input
              aria-label="Question"
              onValueChange={setText}
              placeholder={askHint(selected.length)}
              value={text}
            />
            <button
              aria-label="Ask"
              className="desk-send"
              disabled={busy || text.trim() === ""}
              type="submit"
            >
              <ArrowUp aria-hidden="true" size={16} />
            </button>
          </form>
        </>
      }
      stage={
        <>
          {page === undefined ? (
            <ModelStage document={document} spaces={selected.map((entity) => entity.label)} />
          ) : (
            <Viewer
              documentId={document.id}
              focus={focus}
              marks={{
                answerIds,
                entities: document.entities,
                evidence:
                  hotStep !== undefined && hotStep.entityIds.length === 0 ? hotStep.marks : [],
                hotIds,
                labels: new Map([
                  ...tourLabels(tourStep, tourRoom),
                  ...translationLabels(source, translation),
                  ...labelsOf(derivation),
                ]),
                onHover: (id) => {
                  hoverEntities(id === null ? null : [id]);
                },
                onSelect: pick,
                selectedIds,
              }}
              measure={measureOf(measuring, setMeasuring)}
              onPainted={() => {
                setPainted(true);
              }}
              page={page}
            >
              <ScaleCard
                documentId={document.id}
                onClose={() => {
                  setMeasuring(null);
                }}
                onRedo={() => {
                  setMeasuring([]);
                }}
                onScaled={(patch) => {
                  setMeasuring(null);
                  onScaled(patch);
                }}
                points={measuring}
              />
              <Picked
                entities={selected}
                onAsk={ask}
                onClear={() => {
                  setSelectedIds([]);
                }}
                onRemove={(id) => {
                  setSelectedIds((current) => current.filter((other) => other !== id));
                }}
              />
            </Viewer>
          )}
          <div className="absolute right-3 bottom-3 left-3 lg:right-[436px]">
            <DrawingStrip
              currentId={sampleId}
              disabled={busy}
              onFile={onFile}
              onOpen={onOpen}
              onRemove={(id) => {
                void remove(id);
              }}
              samples={samples}
            />
          </div>
        </>
      }
    >
      <Onboarding
        documentId={document.id}
        phase={tourPhaseOf({ busy, failed, run })}
        picked={selected.length > 0}
        ready={painted}
        room={tourRoom}
      />
    </Shell>
  );
};

const Reading = ({
  name,
  sampleId,
}: {
  readonly name: string;
  readonly sampleId: string | null;
}) => {
  const step = useReadingStep(sampleId);

  return (
    <Shell
      card={
        <>
          <CardHead document={null} />
          <div className="flex flex-col gap-5 px-[18px] py-5">
            <Skeleton />
            <span className="desk-bar h-28 w-full" />
          </div>
        </>
      }
      stage={
        <StageNote busy>
          <LoadingScene step={step} />
          <p aria-live="polite" className="text-lg font-medium">
            {readingSteps[step]}
          </p>
          <p className="desk-fine">
            {name === "" ? "Reading the drawing" : `Reading ${name}`}. Step {String(step + 1)} of{" "}
            {String(readingSteps.length)}.
          </p>
        </StageNote>
      }
    />
  );
};

const Stopped = ({ children }: { readonly children: ReactNode }) => (
  <Shell
    card={
      <>
        <CardHead document={null} />
        <div className="flex flex-col gap-4 px-[18px] py-5">{children}</div>
      </>
    }
    stage={
      <StageNote>
        <p className="text-lg font-medium">No drawing is open</p>
        <p className="desk-fine">Drop a {acceptedLabel} file on this page.</p>
      </StageNote>
    }
  />
);

const Flow = ({
  onFile,
  onOpened,
}: {
  readonly onFile: (file: File) => void;
  readonly onOpened: () => void;
}) => {
  const state = useAtomValue(deskFlow.state);
  const send = useAtomSet(deskFlow.send);

  const retry = () => {
    send({ type: "RETRY" });
  };

  const openId =
    AsyncResult.isSuccess(state) && state.value.context.document !== null
      ? state.value.context.sample
      : null;

  const linkedRef = useRef(false);

  useEffect(() => {
    if (openId === null) {
      return;
    }

    const linked = linkedRef.current ? null : linkedDrawing();

    linkedRef.current = true;

    if (linked !== null && linked !== openId) {
      send({ sample: linked, type: "OPEN" });
    } else {
      linkDrawing(openId);
    }
  }, [openId, send]);

  return AsyncResult.match(state, {
    onFailure: () => (
      <Stopped>
        <p role="alert">The desk did not start. Reload the page.</p>
      </Stopped>
    ),
    onInitial: () => <Reading name="" sampleId={null} />,
    onSuccess: ({ value }) => {
      const { document, run, upload } = value.context;

      const phase = Match.value(value).pipe(
        Match.tag("openFailed", () => "closed"),
        Match.tag("askFailed", () => "failed"),
        Match.tag("starting", "waiting", "polling", () => "busy"),
        Match.orElse(() => "idle"),
      );

      if (phase === "closed") {
        return (
          <Stopped>
            <ProblemNote onRetry={retry} text="This drawing could not be read." />
            <p className="desk-fine">
              Retry opens the same drawing again. An image or a scan is read on a GPU server, which
              can be busy or off. A PDF, DXF or IFC drawing does not need it.
            </p>
            <Button
              data-testid="open-sample"
              onClick={() => {
                send({ sample: firstSample, type: "OPEN" });
              }}
            >
              Open the sample floor plan
            </Button>
          </Stopped>
        );
      }

      return document === null ? (
        <Reading
          name={upload?.name ?? ""}
          sampleId={Predicate.isTagged(value, "uploading") ? null : value.context.sample}
        />
      ) : (
        <Desk
          key={document.id}
          busy={phase === "busy"}
          document={document}
          failed={phase === "failed"}
          onAsk={(text, about) => {
            send({ about, text, type: "ASK" });
          }}
          onBack={() => {
            send({ type: "CLEAR" });
          }}
          onScaled={(patch) => {
            send({ patch, type: "SCALED" });
          }}
          onFile={onFile}
          onOpen={(sample) => {
            onOpened();
            send({ sample, type: "OPEN" });
          }}
          onRetry={retry}
          run={run}
          sampleId={value.context.sample}
        />
      );
    },
  });
};

export const DeskScreen = () => {
  const send = useAtomSet(deskFlow.send);
  const [refused, setRefused] = useState("");

  const addFile = (file: File) => {
    if (isAccepted(file)) {
      setRefused("");
      send({ file, type: "UPLOAD" });
    } else {
      setRefused(`${file.name} is not a drawing file. Use a ${acceptedLabel} file.`);
    }
  };

  return (
    <>
      <Flow
        onFile={addFile}
        onOpened={() => {
          setRefused("");
        }}
      />
      <DropZone onFile={addFile} />
      {refused === "" ? null : (
        <p
          className="desk-card fixed top-4 left-1/2 z-40 -translate-x-1/2 rounded-full px-4 py-2"
          role="alert"
        >
          {refused}
        </p>
      )}
    </>
  );
};
