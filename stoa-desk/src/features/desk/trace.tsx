import { Collapsible, CollapsiblePanel, CollapsibleTrigger } from "@ui-sdk/react/collapsible";
import { Check, ChevronDown, LoaderCircle, X } from "lucide-react";

import type { Run, Step } from "#/domain/desk.ts";

import { DataView } from "./data-view.tsx";
import type { DataLinks } from "./data-view.tsx";
import { parseJson, secondsLabel } from "./format.ts";

const Status = ({ settled, step }: { readonly settled: boolean; readonly step: Step }) => {
  if (!step.done && !settled) {
    return <LoaderCircle aria-label="Running" className="desk-spin" size={14} />;
  }

  return step.ok ? (
    <Check aria-label="Done" className="desk-ok" size={14} />
  ) : (
    <X aria-label="Failed" className="desk-bad" size={14} />
  );
};

export interface TraceProps {
  readonly hotIds: ReadonlySet<string>;
  readonly hotStepId: string | null;
  readonly onHoverEntities: (ids: readonly string[] | null) => void;
  readonly onHoverStep: (step: Step | null) => void;
  readonly onSelectEntity: (id: string) => void;
  readonly onShowStep: (step: Step) => void;
  readonly run: Run;
}

interface StepRowProps extends Omit<TraceProps, "run"> {
  readonly index: number;
  readonly settled: boolean;
  readonly step: Step;
}

const StepRow = ({
  hotIds,
  hotStepId,
  index,
  onHoverEntities,
  onHoverStep,
  onSelectEntity,
  onShowStep,
  settled,
  step,
}: StepRowProps) => {
  const data = parseJson(step.dataJson);

  const links: DataLinks = {
    hotIds,
    links: new Map(step.rowLinks.map((link) => [link.path, link.entityIds])),
    onHover: onHoverEntities,
    onSelect: onSelectEntity,
  };

  const touched = step.entityIds.some((id) => hotIds.has(id));
  const openable = step.kind === "tool" && data !== undefined && step.ok;

  return (
    <li
      className="desk-step"
      data-hot={hotStepId === step.id || touched}
      data-step={step.id}
      onPointerEnter={() => {
        onHoverStep(step);
      }}
      onPointerLeave={() => {
        onHoverStep(null);
      }}
    >
      <Collapsible>
        <CollapsibleTrigger
          className="desk-step-head"
          disabled={!openable}
          onClick={() => {
            onShowStep(step);
          }}
        >
          <span className="desk-step-index tabular-nums">{index + 1}</span>
          <span className="flex min-w-0 flex-1 flex-col text-left">
            <span>{step.sentence}</span>
            {step.method === "model" ? (
              <span className="desk-fine">A trained recognition model did this step.</span>
            ) : null}
          </span>
          <Status settled={settled} step={step} />
          {openable ? <ChevronDown aria-hidden="true" className="desk-chevron" size={14} /> : null}
        </CollapsibleTrigger>
        {openable ? (
          <CollapsiblePanel className="desk-step-body">
            <DataView links={links} value={data} />
          </CollapsiblePanel>
        ) : null}
      </Collapsible>
    </li>
  );
};

export const Trace = ({ run, ...rest }: TraceProps) => {
  const settled = run.status !== "running";

  return (
    <section aria-label="How the agent worked" className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between">
        <h2 className="desk-heading">Step by step</h2>
        <p className="desk-fine tabular-nums">{settled ? secondsLabel(run.elapsedMs) : ""}</p>
      </header>
      <ol className="flex flex-col">
        {run.steps.map((step, index) => (
          <StepRow index={index} key={step.id} settled={settled} step={step} {...rest} />
        ))}
        {settled ? null : (
          <li className="desk-step desk-fine flex items-center gap-2 py-2 pl-2">
            <LoaderCircle aria-hidden="true" className="desk-spin" size={14} />
            Working on the next step
          </li>
        )}
      </ol>
    </section>
  );
};
