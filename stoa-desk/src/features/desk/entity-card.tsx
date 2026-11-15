import { Button } from "@ui-sdk/react/button";
import { X } from "lucide-react";

import type { Entity } from "#/domain/desk.ts";

import { FactRows } from "./facts-panel.tsx";

const questionsFor = (entity: Entity): readonly string[] => {
  const number = entity.facts.find((fact) => fact.key === "Number")?.value ?? "";

  if (entity.kind === "room" && number !== "") {
    return [
      `What is the area of room ${number}?`,
      `How many doors and windows does room ${number} have?`,
    ];
  }

  if (entity.kind === "apartment") {
    const name = `${entity.label.charAt(0).toLowerCase()}${entity.label.slice(1)}`;

    return [
      `What is the net floor area of ${name} without balconies?`,
      `How many rooms does ${name} have?`,
    ];
  }

  if (entity.kind === "door" || entity.kind === "fixture") {
    return [`How many ${entity.group}s are drawn on this floor plan?`];
  }

  return [];
};

const numberOf = (entity: Entity, key: string): number | null => {
  const value = entity.facts.find((fact) => fact.key === key)?.value ?? null;
  const number = value === null ? Number.NaN : Number(value);

  return Number.isFinite(number) ? number : null;
};

const listed = (items: readonly string[]): string =>
  items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items.at(-1) ?? ""}`;

const kindCounts = (entities: readonly Entity[]): string => {
  const counts = new Map<string, number>();

  for (const entity of entities) {
    counts.set(entity.kind, (counts.get(entity.kind) ?? 0) + 1);
  }

  return [...counts]
    .map(([kind, count]) => `${String(count)} ${kind}${count === 1 ? "" : "s"}`)
    .join(", ");
};

export const selectionQuestions = (entities: readonly Entity[]): readonly string[] => {
  const [first] = entities;

  if (first === undefined) {
    return [];
  }

  if (entities.length === 1) {
    const own = questionsFor(first);

    if (own.length > 0) {
      return own;
    }

    return first.kind === "room"
      ? ["What is the area of this room?", "How many doors does this room have?"]
      : ["What does the drawing say about this?"];
  }

  const many = questionsForMany(entities);
  const rooms = entities.every((entity) => entity.kind === "room");

  if (many.length > 0) {
    return many;
  }

  return rooms
    ? ["What is the total area of these rooms?", "How many doors do these rooms have?"]
    : ["How many items of each kind are selected?"];
};

const questionsForMany = (entities: readonly Entity[]): readonly string[] => {
  const numbers = entities.flatMap((entity) => {
    const number = entity.facts.find((fact) => fact.key === "Number")?.value ?? null;

    return entity.kind === "room" && number !== null ? [number] : [];
  });

  return numbers.length < 2
    ? []
    : [
        `What is the total area of rooms ${listed(numbers)}?`,
        `Which of rooms ${listed(numbers)} is the largest?`,
      ];
};

const stopPointer = (event: { readonly stopPropagation: () => void }) => {
  event.stopPropagation();
};

export interface SelectionCardProps {
  readonly entities: readonly Entity[];
  readonly onAsk: (question: string) => void;
  readonly onClose: () => void;
  readonly onRemove: (id: string) => void;
}

export const SelectionCard = ({ entities, onAsk, onClose, onRemove }: SelectionCardProps) => {
  const areas = entities.flatMap((entity) => numberOf(entity, "Area") ?? []);
  const total = areas.reduce((sum, area) => sum + area, 0);

  return (
    <aside
      aria-label="Selected elements"
      className="desk-card desk-float absolute top-16 left-4 flex max-h-[60%] w-80 flex-col gap-2 overflow-y-auto"
      data-testid="selection-card"
      onPointerDown={stopPointer}
      onWheel={stopPointer}
    >
      <header className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">{String(entities.length)} selected</h2>
        <Button
          aria-label="Clear the selection"
          data-size="icon"
          data-variant="ghost"
          onClick={onClose}
        >
          <X aria-hidden="true" size={14} />
        </Button>
      </header>
      <p className="desk-fine">{kindCounts(entities)}</p>
      {areas.length === 0 ? null : (
        <p className="flex items-baseline justify-between gap-2">
          <span className="desk-fine">
            Total area
            {areas.length === entities.length
              ? ""
              : `, ${String(areas.length)} of ${String(entities.length)} have one`}
          </span>
          <span className="text-xl font-semibold tabular-nums">{total.toFixed(2)} m²</span>
        </p>
      )}
      <ul className="desk-facts">
        {entities.map((entity) => {
          const area = numberOf(entity, "Area");

          return (
            <li className="flex items-center justify-between gap-2 py-1" key={entity.id}>
              <span className="truncate">{entity.label}</span>
              <span className="flex shrink-0 items-center gap-1 tabular-nums">
                {area === null ? <span className="desk-dash">–</span> : `${area.toFixed(2)} m²`}
                <Button
                  aria-label={`Remove ${entity.label}`}
                  data-size="icon"
                  data-variant="ghost"
                  onClick={() => {
                    onRemove(entity.id);
                  }}
                >
                  <X aria-hidden="true" size={12} />
                </Button>
              </span>
            </li>
          );
        })}
      </ul>
      {questionsForMany(entities).map((question) => (
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
    </aside>
  );
};

export interface EntityCardProps {
  readonly entity: Entity;
  readonly onAsk: (question: string) => void;
  readonly onClose: () => void;
}

export const EntityCard = ({ entity, onAsk, onClose }: EntityCardProps) => (
  <aside
    aria-label={entity.label}
    className="desk-card desk-float absolute top-16 left-4 flex max-h-[60%] w-80 flex-col gap-2 overflow-y-auto"
    data-testid="entity-card"
    onPointerDown={(event) => {
      event.stopPropagation();
    }}
    onWheel={(event) => {
      event.stopPropagation();
    }}
  >
    <header className="flex items-center justify-between gap-2">
      <h2 className="font-semibold">{entity.label}</h2>
      <Button aria-label="Close" data-size="icon" data-variant="ghost" onClick={onClose}>
        <X aria-hidden="true" size={14} />
      </Button>
    </header>
    <FactRows facts={entity.facts} />
    {questionsFor(entity).map((question) => (
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
  </aside>
);
