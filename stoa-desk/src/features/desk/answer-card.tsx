import { Number as Numbers, Predicate } from "effect";
import { ArrowRight, CircleAlert, CircleCheck, CircleX } from "lucide-react";

import type { Answer, Check as CheckRow, Derivation, Operand } from "#/domain/desk.ts";

import { numberLabel, percentLabel, unitLabel, valueLabel } from "./format.ts";

const bars = Array.from({ length: 32 }, (_unused, index) => index);

const sizeFor = (text: string): "big" | "mid" | "small" => {
  if (text.length <= 7) {
    return "big";
  }

  return text.length <= 12 ? "mid" : "small";
};

const Meter = ({ answer }: { readonly answer: Answer }) => {
  const { level, modelClaim, score } = answer.confidence;

  if (score === null) {
    return null;
  }

  const lit = Math.round(score * bars.length);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <span className="desk-heading">Confidence</span>
        <span className="font-medium tabular-nums">{percentLabel(score)}</span>
      </div>
      <div aria-hidden="true" className="desk-meter" data-level={level}>
        {bars.map((bar) => (
          <span data-on={bar < lit} key={bar} style={{ "--i": bar }} />
        ))}
      </div>
      <p className="desk-fine">
        Measured from the checks below.
        {modelClaim === null
          ? ""
          : ` The AI model claimed ${percentLabel(modelClaim)}. The score does not use it.`}
      </p>
    </div>
  );
};

const CheckIcon = ({ check }: { readonly check: CheckRow }) => {
  if (check.state === "pass") {
    return <CircleCheck aria-label="Passed" className="mt-0.5 shrink-0" size={15} />;
  }

  return check.state === "warn" ? (
    <CircleAlert aria-label="Doubt" className="desk-warn mt-0.5 shrink-0" size={15} />
  ) : (
    <CircleX aria-label="Failed" className="desk-bad mt-0.5 shrink-0" size={15} />
  );
};

export interface Linked {
  readonly hotIds: ReadonlySet<string>;
  readonly onHoverEntities: (ids: readonly string[] | null) => void;
  readonly onSelectEntity: (id: string) => void;
}

const sizeOf = (row: Operand | Derivation): number =>
  Predicate.isNumber(row.value) && row.value > 0 ? row.value : 0;

export const Sources = ({
  derivation,
  hotIds,
  onHoverEntities,
  onSelectEntity,
}: Linked & { readonly derivation: Derivation }) => {
  const rows = derivation.operands.length > 0 ? derivation.operands : [derivation];
  const total = Numbers.sumAll(rows.map(sizeOf));
  const stacked = rows.length > 1 && rows.every((row) => sizeOf(row) > 0);

  const handlers = (row: Operand | Derivation) => ({
    onClick: () => {
      const [first] = row.entityIds;

      if (first !== undefined) {
        onSelectEntity(first);
      }
    },
    onPointerEnter: () => {
      onHoverEntities(row.entityIds.length > 0 ? row.entityIds : null);
    },
    onPointerLeave: () => {
      onHoverEntities(null);
    },
  });

  return (
    <section aria-label="Where the value comes from" className="flex flex-col gap-2">
      <h2 className="desk-heading">Built from</h2>
      {stacked ? (
        <div className="desk-stack">
          {rows.map((row) => (
            <button
              aria-label={`${row.label}: ${valueLabel(row.value)}`}
              className="desk-segment"
              data-hot={row.entityIds.some((id) => hotIds.has(id))}
              key={`${row.path}:${row.label}`}
              style={{ flexGrow: sizeOf(row) / total }}
              type="button"
              {...handlers(row)}
            />
          ))}
        </div>
      ) : null}
      <ul className="flex flex-col">
        {rows.map((row) => (
          <li key={`${row.path}:${row.label}`}>
            <button
              className="desk-source"
              data-hot={row.entityIds.some((id) => hotIds.has(id))}
              type="button"
              {...handlers(row)}
            >
              <span className="truncate">{row.label}</span>
              <span className="font-medium tabular-nums">
                {Predicate.isNumber(row.value)
                  ? numberLabel(Math.round(row.value * 100) / 100)
                  : row.value}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
};

const Asked = ({
  about,
  question,
}: {
  readonly about: readonly string[];
  readonly question: string;
}) => (
  <div className="flex flex-col gap-1">
    <p className="desk-question">{question}</p>
    {about.length === 0 ? null : (
      <p className="desk-fine" data-testid="answer-about">
        About {about.slice(0, 4).join(", ")}
        {about.length > 4 ? ` and ${String(about.length - 4)} more` : ""}
      </p>
    )}
  </div>
);

export const Hero = ({
  about,
  answer,
  question,
}: {
  readonly about: readonly string[];
  readonly answer: Answer;
  readonly question: string;
}) => {
  if (answer.status !== "answered") {
    return (
      <section aria-label="Answer" className="flex flex-col gap-3" data-testid="answer">
        <Asked about={about} question={question} />
        <p className="desk-figure" data-state="none">
          No answer
        </p>
        {answer.abstain === null ? null : (
          <>
            <p>{answer.abstain.detail}</p>
            {answer.abstain.request === "" ? null : (
              <p className="desk-need">
                <ArrowRight aria-hidden="true" className="mt-0.5 shrink-0" size={15} />
                {answer.abstain.request}
              </p>
            )}
          </>
        )}
        {answer.bestEstimate === null ? null : (
          <div className="flex flex-col gap-1" data-testid="estimate">
            <h2 className="desk-heading">Best estimate, not checked</h2>
            <p className="text-2xl font-medium tabular-nums">
              {valueLabel(answer.bestEstimate)}
              <span className="desk-unit"> {unitLabel(answer.unit)}</span>
            </p>
          </div>
        )}
      </section>
    );
  }

  const text = valueLabel(answer.value);

  return (
    <section aria-label="Answer" className="flex flex-col gap-4" data-testid="answer">
      <Asked about={about} question={question} />
      <p className="desk-figure" data-size={sizeFor(text)}>
        {text}
        <span className="desk-unit"> {unitLabel(answer.unit)}</span>
      </p>
      {answer.margin === null ? null : (
        <p className="desk-margin" data-testid="answer-margin">
          <span className="font-medium tabular-nums">
            {answer.margin.text} {unitLabel(answer.unit)} error margin
          </span>
          <span className="desk-fine">{answer.margin.basis}</span>
        </p>
      )}
      <Meter answer={answer} />
    </section>
  );
};

export interface ChecksProps {
  readonly answer: Answer;
  readonly hotStepId: string | null;
  readonly onHoverStepId: (id: string | null) => void;
}

export const Checks = ({ answer, hotStepId, onHoverStepId }: ChecksProps) => {
  if (answer.confidence.checks.length === 0) {
    return (
      <p className="desk-fine">
        There is no answer to check. The agent gives no number that it cannot trace to the drawing.
      </p>
    );
  }

  return (
    <ul aria-label="Why this confidence" className="flex flex-col gap-0.5">
      {answer.confidence.checks.map((check) => (
        <li
          className="desk-check"
          data-hot={check.stepId !== null && check.stepId === hotStepId}
          key={check.id}
          onPointerEnter={() => {
            onHoverStepId(check.stepId);
          }}
          onPointerLeave={() => {
            onHoverStepId(null);
          }}
        >
          <CheckIcon check={check} />
          <span className="flex min-w-0 flex-col">
            <span className="font-medium">{check.label}</span>
            <span className="desk-fine">{check.detail}</span>
          </span>
        </li>
      ))}
      {answer.convention === "" ? null : (
        <li className="desk-fine px-2 pt-2">How it was counted: {answer.convention}</li>
      )}
    </ul>
  );
};
