import { Option, Schema } from "effect";
import { useEffect, useState } from "react";

const walls =
  "M20 20H300V200H20Z M20 96H132 M132 20V132 M132 132H196 M196 96V200 M196 96H300 M236 20V96 M84 96V200";

const rooms = [
  "20,20 132,20 132,96 20,96",
  "132,20 236,20 236,96 196,96 196,132 132,132",
  "236,20 300,20 300,96 236,96",
  "196,96 300,96 300,200 196,200",
  "84,96 132,96 132,132 196,132 196,200 84,200",
  "20,96 84,96 84,200 20,200",
];

const slabs = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];

export const readingSteps = [
  "Sending the file",
  "Opening the file",
  "Finding the walls, the scale and the text",
  "Listing the rooms, the doors and the other facts",
  "Checking the facts against each other",
];

const Stage = Schema.Struct({ stage: Schema.Finite });

const decodeStage = Schema.decodeUnknownOption(Stage);

export const useReadingStep = (sampleId: string | null): number => {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (sampleId === null) {
      return;
    }

    const ask = async () => {
      const response = await fetch(`/api/sample?id=${sampleId}&part=stage`).catch(() => null);
      const body: unknown = response?.ok === true ? await response.json().catch(() => null) : null;

      const stage = Option.match(decodeStage(body), {
        onNone: () => 1,
        onSome: (found) => Math.max(1, Math.min(readingSteps.length - 1, found.stage)),
      });

      setStep((current) => Math.max(current, stage));
    };

    void ask();

    const timer = setInterval(() => {
      void ask();
    }, 350);

    return () => {
      clearInterval(timer);
    };
  }, [sampleId]);

  return sampleId === null ? 0 : Math.max(1, step);
};

const Plan = ({ className }: { readonly className: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 320 220">
    <path d={walls} pathLength={1} />
  </svg>
);

export const LoadingScene = ({ step }: { readonly step: number }) => (
  <div aria-hidden="true" className="desk-scene" data-step={step}>
    <div className="desk-scene-plane">
      <span className="desk-scene-sheet" />
      <svg className="desk-scene-rooms" data-on={step >= 4} viewBox="0 0 320 220">
        {rooms.map((points, index) => (
          <polygon key={points} points={points} style={{ "--i": index }} />
        ))}
      </svg>
      <span className="desk-scene-ink" data-on={step >= 2}>
        <Plan className="desk-scene-lines" />
      </span>
      {slabs.map((slab) => (
        <span
          className="desk-scene-slab"
          data-on={step >= 3}
          data-top={slab === slabs.length - 1}
          key={slab}
          style={{ "--k": slab }}
        >
          <Plan className="desk-scene-wall" />
        </span>
      ))}
      <span className="desk-scene-beam" data-on={step >= 2} />
    </div>
  </div>
);
