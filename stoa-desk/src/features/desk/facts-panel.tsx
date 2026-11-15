import { Number as Numbers } from "effect";
import { useState } from "react";
import type { ReactNode } from "react";

import type { DrawingDocument, Entity, Fact } from "#/domain/desk.ts";

export const StatusDot = ({ status }: { readonly status: Fact["status"] }) => (
  <span className="desk-dot" data-status={status} title={status} />
);

export const FactValue = ({ fact }: { readonly fact: Fact }) =>
  fact.value === null ? (
    <span className="desk-dash">–</span>
  ) : (
    <>
      {fact.value}
      {fact.unit === "" ? "" : ` ${fact.unit}`}
    </>
  );

const plainSources = new Map([
  ["OCR", "read as text"],
  ["count_door_swings", "door swings found on the drawing"],
  ["count_symbols", "symbols counted on the drawing"],
  ["list_apartments", "rooms grouped by apartment"],
  ["list_rooms", "read from the drawing"],
  ["read_scales", "scale printed on the drawing"],
  ["room_area", "measured from the room outline"],
  ["room_perimeter", "measured along the room outline"],
]);

const plainSource = (source: string): string => plainSources.get(source) ?? source;

const statusWords = {
  estimated: "Estimated. It is measured or recognised on the drawing, so it can be wrong.",
  known: "Known. It is read directly from the drawing.",
  unknown: "Not known. The drawing does not give it.",
} satisfies Record<Fact["status"], string>;

const sureWords = (fact: Fact): string => {
  if (fact.confidence === undefined) {
    return "Not measured yet. There is no test result for this kind of fact.";
  }

  if (fact.status === "unknown") {
    return "0%: there is no value.";
  }

  return `${(fact.confidence * 100).toFixed(fact.confidence > 0.99 ? 1 : 0)}% sure`;
};

export const FactDetail = ({
  children,
  fact,
}: {
  readonly children?: ReactNode;
  readonly fact: Fact;
}) => (
  <dl className="desk-detail" data-testid="fact-detail">
    <div>
      <dt>Status</dt>
      <dd className="flex items-start gap-2">
        <span className="flex h-[1.45em] shrink-0 items-center">
          <StatusDot status={fact.status} />
        </span>
        <span>{statusWords[fact.status]}</span>
      </dd>
    </div>
    <div data-testid="fact-confidence">
      <dt>Confidence</dt>
      <dd>
        {fact.confidence === undefined ? null : (
          <span className="desk-gauge">
            <span style={{ width: `${String(fact.confidence * 100)}%` }} />
          </span>
        )}
        {sureWords(fact)}
        {fact.basis === undefined ? null : <span className="desk-basis">{fact.basis}</span>}
      </dd>
    </div>
    {fact.margin === undefined ? null : (
      <div data-testid="fact-margin">
        <dt>Error margin</dt>
        <dd>
          <span className="tabular-nums">{fact.margin}</span>
          {fact.marginBasis === undefined ? null : (
            <span className="desk-basis">{fact.marginBasis}</span>
          )}
        </dd>
      </div>
    )}
    <div>
      <dt>How it was measured</dt>
      <dd>
        {plainSource(fact.source)}
        {fact.note === "" ? "" : `. ${fact.note}`}
      </dd>
    </div>
    {children}
  </dl>
);

export const FactRows = ({ facts }: { readonly facts: readonly Fact[] }) => {
  const [openKey, setOpenKey] = useState<string | null>(null);

  return (
    <ul className="desk-facts">
      {facts.map((fact) => (
        <li key={fact.key}>
          <button
            aria-expanded={openKey === fact.key}
            className="desk-fact"
            onClick={() => {
              setOpenKey((current) => (current === fact.key ? null : fact.key));
            }}
            type="button"
          >
            <span className="desk-fine">{fact.key}</span>
            <span className="flex items-center justify-end gap-2 font-medium tabular-nums">
              <FactValue fact={fact} />
              {fact.margin === undefined ? null : (
                <span className="desk-fine font-normal">
                  {fact.margin.split(" ").slice(0, 2).join(" ")}
                </span>
              )}
              <StatusDot status={fact.status} />
            </span>
          </button>
          {openKey === fact.key ? <FactDetail fact={fact} /> : null}
        </li>
      ))}
    </ul>
  );
};

const singular = (word: string): string => (word.endsWith("s") ? word.slice(0, -1) : word);

const entitiesFor = (fact: Fact, entities: readonly Entity[]): readonly Entity[] => {
  const key = fact.key.toLowerCase();

  if (key.startsWith("scale")) {
    return entities.filter((entity) => entity.kind === "scale");
  }

  if (key.startsWith("rooms with")) {
    return entities.filter((entity) => entity.kind === "room" && entity.geometry === "polygon");
  }

  if (key.startsWith("room")) {
    return entities.filter((entity) => entity.kind === "room");
  }

  if (key.startsWith("door")) {
    return entities.filter((entity) => entity.kind === "door");
  }

  if (key.startsWith("text")) {
    return entities.filter((entity) => entity.kind === "label");
  }

  return entities.filter(
    (entity) => entity.group === singular(key) || entity.kind === singular(key),
  );
};

const confidencesOf = (entities: readonly Entity[]): readonly number[] =>
  entities.flatMap((entity) =>
    entity.facts.flatMap((fact) => (fact.confidence === undefined ? [] : [fact.confidence])),
  );

const Spread = ({ marks }: { readonly marks: readonly Entity[] }) => {
  const values = confidencesOf(marks);

  if (marks.length === 0) {
    return null;
  }

  return (
    <>
      <div>
        <dt>On the drawing</dt>
        <dd>
          {String(marks.length)} {marks.length === 1 ? "place is" : "places are"} marked. Click one
          on the drawing for its own facts.
        </dd>
      </div>
      {values.length === 0 ? null : (
        <div>
          <dt>Confidence per place</dt>
          <dd>
            Lowest {(Math.min(...values) * 100).toFixed(0)}%, average{" "}
            {((Numbers.sumAll(values) / values.length) * 100).toFixed(0)}%
          </dd>
        </div>
      )}
    </>
  );
};

const areaOf = (entity: Entity): number | null => {
  const value = entity.facts.find((fact) => fact.key === "Area")?.value ?? null;
  const area = value === null ? Number.NaN : Number(value);

  return Number.isFinite(area) ? area : null;
};

export interface FactsPanelProps {
  readonly document: DrawingDocument;
  readonly hotIds: ReadonlySet<string>;
  readonly onHoverEntities: (ids: readonly string[] | null) => void;
  readonly onSelectEntity: (id: string) => void;
  readonly onShowEntities: (ids: readonly string[]) => void;
}

const statuses = ["known", "estimated", "unknown"] satisfies readonly Fact["status"][];

export const FactsPanel = ({
  document,
  hotIds,
  onHoverEntities,
  onSelectEntity,
  onShowEntities,
}: FactsPanelProps) => {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const openFact = document.summary.find((fact) => fact.key === openKey);

  const rooms = document.entities
    .flatMap((entity) => (entity.kind === "room" ? [{ area: areaOf(entity), entity }] : []))
    .toSorted((a, b) => (b.area ?? 0) - (a.area ?? 0));

  const largest = Math.max(1, ...rooms.map((room) => room.area ?? 0));

  return (
    <div className="flex flex-col gap-6">
      <section aria-label="What the drawing gives" className="flex flex-col gap-2">
        <header className="flex items-baseline justify-between">
          <h2 className="desk-heading">This drawing</h2>
          <p className="desk-fine flex items-center gap-3">
            {statuses.map((status) => (
              <span className="flex items-center gap-1" key={status}>
                <StatusDot status={status} />
                {status}
              </span>
            ))}
          </p>
        </header>
        <ul className="grid grid-cols-3 gap-2">
          {document.summary.map((fact) => (
            <li key={fact.key}>
              <button
                aria-expanded={openKey === fact.key}
                className="desk-tile"
                onClick={() => {
                  setOpenKey((current) => (current === fact.key ? null : fact.key));
                  onShowEntities(entitiesFor(fact, document.entities).map((entity) => entity.id));
                }}
                onPointerEnter={() => {
                  onHoverEntities(entitiesFor(fact, document.entities).map((entity) => entity.id));
                }}
                onPointerLeave={() => {
                  onHoverEntities(null);
                }}
                type="button"
              >
                <span className="flex items-center justify-between gap-1">
                  <span className="text-xl leading-none font-semibold tabular-nums">
                    <FactValue fact={fact} />
                  </span>
                  <StatusDot status={fact.status} />
                </span>
                <span className="desk-fine">{fact.key}</span>
              </button>
            </li>
          ))}
        </ul>
        {openFact === undefined ? (
          <p className="desk-fine">Click a number to see how it was measured.</p>
        ) : (
          <FactDetail fact={openFact}>
            <Spread marks={entitiesFor(openFact, document.entities)} />
          </FactDetail>
        )}
      </section>

      {document.conflicts.length === 0 ? null : (
        <section aria-label="Facts that do not add up" className="flex flex-col gap-2">
          <h2 className="desk-heading">Does not add up</h2>
          <ul className="flex flex-col gap-1.5">
            {document.conflicts.map((conflict) => (
              <li key={conflict.id}>
                <button
                  className="desk-conflict"
                  onClick={() => {
                    onShowEntities(conflict.entityIds);
                  }}
                  type="button"
                >
                  {conflict.text}
                </button>
              </li>
            ))}
          </ul>
          <p className="desk-fine">An answer that uses one of these gets a lower confidence.</p>
        </section>
      )}

      {document.unknown.length === 0 ? null : (
        <section aria-label="What the drawing does not give" className="flex flex-col gap-2">
          <h2 className="desk-heading">Not on this drawing</h2>
          <ul className="flex flex-wrap gap-1.5">
            {document.unknown.map((item) => (
              <li className="desk-absent" key={item}>
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      {rooms.length === 0 ? null : (
        <section aria-label="Rooms" className="flex flex-col gap-2">
          <h2 className="desk-heading">Rooms by area, m²</h2>
          <ul className="flex flex-col">
            {rooms.map(({ area, entity }) => (
              <li key={entity.id}>
                <button
                  className="desk-room"
                  data-hot={hotIds.has(entity.id)}
                  onClick={() => {
                    onSelectEntity(entity.id);
                  }}
                  onPointerEnter={() => {
                    onHoverEntities([entity.id]);
                  }}
                  onPointerLeave={() => {
                    onHoverEntities(null);
                  }}
                  type="button"
                >
                  <span className="truncate text-left">{entity.label}</span>
                  <span className="desk-room-track">
                    <span
                      className="desk-room-bar"
                      style={{ width: `${String(((area ?? 0) / largest) * 100)}%` }}
                    />
                  </span>
                  <span className="text-right tabular-nums">
                    {area === null ? <span className="desk-dash">–</span> : area.toFixed(2)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
