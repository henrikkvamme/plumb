import { Input } from "@ui-sdk/react/input";
import { X } from "lucide-react";
import { useState } from "react";

import { setScale } from "#/api/desk.ts";
import type { Scaled } from "#/domain/desk.ts";

export type MeasurePoint = readonly [number, number];

const hints = [
  "Click the first end of a length you know, such as a dimension line or a door.",
  "Click the other end.",
  "Type the real distance between A and B.",
];

const lengthOf = (text: string): number | null => {
  const value = Number(text.trim().replace(",", "."));

  return Number.isFinite(value) && value > 0 ? value : null;
};

const ScaleTool = ({
  documentId,
  onClose,
  onRedo,
  onScaled,
  points,
}: {
  readonly documentId: string;
  readonly onClose: () => void;
  readonly onRedo: () => void;
  readonly onScaled: (patch: Scaled) => void;
  readonly points: readonly MeasurePoint[];
}) => {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [first, second] = points;
  const length = lengthOf(text);

  const apply = async () => {
    if (first === undefined || second === undefined || length === null || busy) {
      return;
    }

    setBusy(true);
    setProblem("");

    const result = await setScale({
      data: { documentId, lengthM: length, points: [first, second] },
    }).catch(() => null);

    setBusy(false);

    if (result?.ok === true) {
      onScaled(result.value);
    } else {
      setProblem(result?.ok === false ? result.error.reason : "The scale was not set. Try again.");
    }
  };

  return (
    <section
      aria-label="Set the scale"
      className="desk-card desk-float absolute top-16 left-4 flex w-80 flex-col gap-3"
      data-testid="scale-tool"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-medium">Set the scale</h2>
        <button aria-label="Close" className="desk-round" onClick={onClose} type="button">
          <X aria-hidden="true" size={15} />
        </button>
      </div>
      <p className="desk-fine">{hints[Math.min(points.length, 2)]}</p>
      {second === undefined ? null : (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            void apply();
          }}
        >
          <div className="desk-ask">
            <Input
              aria-label="Real distance in metres"
              autoFocus
              inputMode="decimal"
              onValueChange={setText}
              placeholder="Distance, such as 4.2"
              value={text}
            />
            <span className="desk-fine pr-3">m</span>
          </div>
          <div className="flex items-center gap-2">
            <button className="desk-pill" disabled={length === null || busy} type="submit">
              {busy ? "Reading the drawing again" : "Use this scale"}
            </button>
            <button
              className="desk-pill"
              data-quiet=""
              disabled={busy}
              onClick={onRedo}
              type="button"
            >
              Pick again
            </button>
          </div>
        </form>
      )}
      {problem === "" ? null : (
        <p className="desk-fine" data-state="bad" role="alert">
          {problem}
        </p>
      )}
    </section>
  );
};

export const ScaleCard = ({
  points,
  ...rest
}: {
  readonly documentId: string;
  readonly onClose: () => void;
  readonly onRedo: () => void;
  readonly onScaled: (patch: Scaled) => void;
  readonly points: readonly MeasurePoint[] | null;
}) => (points === null ? null : <ScaleTool {...rest} points={points} />);
