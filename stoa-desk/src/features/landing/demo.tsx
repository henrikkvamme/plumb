import { Link } from "@tanstack/react-router";
import { ArrowUp, Check, Minus } from "lucide-react";
import { useState } from "react";
import type { PointerEvent } from "react";

import { BrandMark } from "#/features/desk/brand-mark.tsx";

import {
  areaOf,
  estimateMargin,
  metres,
  perimeterOf,
  planHeight,
  planMetres,
  planWidth,
  clipOf,
  questions,
  rooms,
  sizeOf,
  squareMetres,
  wallPath,
} from "./plan.ts";
import type { FactStatus, Question, Room } from "./plan.ts";

type Selection =
  | { readonly kind: "question"; readonly question: Question }
  | { readonly kind: "room"; readonly index: number; readonly room: Room };

type View = "top" | "3d";

interface Aim {
  readonly x: number;
  readonly y: number;
}

const slabs = Array.from({ length: 22 }, (_, index) => index);

const viewBox = `0 0 ${planWidth} ${planHeight}`;

const litRooms = (selection: Selection): readonly number[] =>
  selection.kind === "room" ? [selection.index] : selection.question.rooms;

const measuredRoom = (selection: Selection): Room | undefined =>
  selection.kind === "room" ? selection.room : rooms[selection.question.measured ?? -1];

const Walls = ({ className }: { readonly className: string }) => (
  <svg aria-hidden="true" className={className} viewBox={viewBox}>
    <path d={wallPath} pathLength={1} />
  </svg>
);

const Measure = ({ room }: { readonly room: Room }) => {
  const [width, height] = sizeOf(room);
  const [x1, x2, y] = room.across;
  const [x, y1, y2] = room.down;

  return (
    <g className="plumb-measure" key={room.name}>
      <path d={`M${x1} ${y}H${x2} M${x1} ${y - 3}v6 M${x2} ${y - 3}v6`} pathLength={1} />
      <path d={`M${x} ${y1}V${y2} M${x - 3} ${y1}h6 M${x - 3} ${y2}h6`} pathLength={1} />
      <text textAnchor="middle" x={(x1 + x2) / 2} y={y - 4}>
        {metres(width)}
      </text>
      <text x={x + 5} y={(y1 + y2) / 2 + 2}>
        {metres(height)}
      </text>
    </g>
  );
};

const RoomTargets = ({
  lit,
  onRoom,
}: {
  readonly lit: readonly number[];
  readonly onRoom: (index: number, room: Room) => void;
}) => (
  <div className="plumb-rooms">
    {rooms.map((room, index) => (
      <button
        aria-label={`${room.name}, ${squareMetres(areaOf(room))}`}
        aria-pressed={lit.includes(index)}
        key={room.name}
        onClick={() => {
          onRoom(index, room);
        }}
        style={{ "--i": lit.indexOf(index), clipPath: clipOf(room) }}
        type="button"
      />
    ))}
  </div>
);

const RoomLabels = ({ selection }: { readonly selection: Selection }) => {
  const measured = measuredRoom(selection);

  return (
    <svg aria-hidden="true" className="plumb-labels" viewBox={viewBox}>
      {rooms.map((room, index) => (
        <g key={room.name} style={{ "--i": index }}>
          <text textAnchor="middle" x={room.label[0]} y={room.label[1]}>
            {room.name}
          </text>
          <text
            className="plumb-label-area"
            textAnchor="middle"
            x={room.label[0]}
            y={room.label[1] + 9}
          >
            {squareMetres(areaOf(room))}
          </text>
        </g>
      ))}
      {measured === undefined ? null : <Measure room={measured} />}
    </svg>
  );
};

const Crosshair = ({ aim }: { readonly aim: Aim | null }) =>
  aim === null ? null : (
    <>
      <span className="plumb-aim plumb-aim-x" style={{ left: `${aim.x * 100}%` }} />
      <span className="plumb-aim plumb-aim-y" style={{ top: `${aim.y * 100}%` }} />
    </>
  );

const aimOf = (event: PointerEvent<HTMLDivElement>): Aim => {
  const box = event.currentTarget.getBoundingClientRect();

  return {
    x: Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)),
    y: Math.min(1, Math.max(0, (event.clientY - box.top) / box.height)),
  };
};

const PlanStage = ({
  onRoom,
  selection,
  view,
}: {
  readonly onRoom: (index: number, room: Room) => void;
  readonly selection: Selection;
  readonly view: View;
}) => {
  const [aim, setAim] = useState<Aim | null>(null);
  const shown = view === "top" ? aim : null;

  return (
    <div className="plumb-plan">
      <div
        className="plumb-plane"
        data-view={view}
        onPointerLeave={() => {
          setAim(null);
        }}
        onPointerMove={(event) => {
          setAim(aimOf(event));
        }}
      >
        <span className="plumb-sheet" />
        <RoomTargets lit={litRooms(selection)} onRoom={onRoom} />
        <Walls className="plumb-lines" />
        {slabs.map((slab) => (
          <span
            className="plumb-slab"
            data-top={slab === slabs.length - 1}
            key={slab}
            style={{ "--k": slab }}
          >
            <Walls className="plumb-wall" />
          </span>
        ))}
        <RoomLabels selection={selection} />
        <Crosshair aim={shown} />
      </div>
      <p aria-hidden="true" className="plumb-readout" data-on={shown !== null}>
        <span>x {planMetres(shown?.x ?? 0, planWidth)} m</span>
        <span>y {planMetres(shown?.y ?? 0, planHeight)} m</span>
      </p>
    </div>
  );
};

const statusWord = (status: FactStatus): string =>
  `${status.charAt(0).toUpperCase()}${status.slice(1)}`;

const Fact = ({
  label,
  status,
  value,
}: {
  readonly label: string;
  readonly status: FactStatus;
  readonly value: string | null;
}) => (
  <li className="plumb-fact">
    <span className="desk-dot" data-status={status} />
    <span>{label}</span>
    <span className="plumb-fact-value">
      {value ?? <Minus aria-label="Unknown" className="size-3.5 opacity-50" />}
    </span>
  </li>
);

const QuestionAnswer = ({ question }: { readonly question: Question }) => (
  <div className="plumb-answer" key={question.id}>
    <p className="plumb-asked">{question.text}</p>
    <p className="plumb-big">{question.answer}</p>
    <p className="plumb-status">
      <span className="desk-dot" data-status={question.status} />
      {statusWord(question.status)}
      <span className="plumb-soft">{question.detail}</span>
    </p>
    <ul className="plumb-checks">
      {question.checks.map((check, index) => (
        <li key={check} style={{ "--i": index }}>
          <span className="plumb-tick" data-status={question.status}>
            {question.status === "unknown" ? (
              <Minus className="size-3" />
            ) : (
              <Check className="size-3" />
            )}
          </span>
          {check}
        </li>
      ))}
    </ul>
  </div>
);

const RoomAnswer = ({ room }: { readonly room: Room }) => (
  <div className="plumb-answer" key={room.name}>
    <p className="plumb-asked">Selected room</p>
    <p className="plumb-big">{room.name}</p>
    <ul className="plumb-facts">
      <Fact
        label="Area"
        status={room.status}
        value={
          room.status === "estimated"
            ? `${squareMetres(areaOf(room))} ± ${estimateMargin.toFixed(1)}`
            : squareMetres(areaOf(room))
        }
      />
      <Fact label="Perimeter" status={room.status} value={metres(perimeterOf(room))} />
      <Fact label="Ceiling height" status="unknown" value={null} />
    </ul>
  </div>
);

const DemoCard = ({
  onAsk,
  selection,
}: {
  readonly onAsk: (question: Question) => void;
  readonly selection: Selection;
}) => (
  <div className="desk-card plumb-card">
    <div className="flex items-center justify-between gap-3">
      <span className="desk-brand flex items-center gap-1.5">
        <BrandMark />
        Plumb
      </span>
      <span className="desk-tag">Apartment, 1:100</span>
    </div>
    <div aria-live="polite" className="plumb-card-body">
      {selection.kind === "question" ? (
        <QuestionAnswer question={selection.question} />
      ) : (
        <RoomAnswer room={selection.room} />
      )}
    </div>
    <ul className="plumb-chips">
      {questions.map((question) => (
        <li key={question.id}>
          <button
            aria-pressed={selection.kind === "question" && selection.question.id === question.id}
            className="plumb-chip"
            onClick={() => {
              onAsk(question);
            }}
            type="button"
          >
            {question.text}
          </button>
        </li>
      ))}
    </ul>
    <Link className="plumb-ask" to="/desk">
      <span>Ask about your drawing</span>
      <span className="plumb-ask-send">
        <ArrowUp className="size-4" />
      </span>
    </Link>
  </div>
);

const ViewSwitch = ({
  onView,
  view,
}: {
  readonly onView: (view: View) => void;
  readonly view: View;
}) => (
  <div className="plumb-switch" data-view={view}>
    <button
      aria-pressed={view === "top"}
      onClick={() => {
        onView("top");
      }}
      type="button"
    >
      Top
    </button>
    <button
      aria-pressed={view === "3d"}
      onClick={() => {
        onView("3d");
      }}
      type="button"
    >
      3D
    </button>
  </div>
);

const [firstQuestion] = questions;

export const Demo = () => {
  const [selection, setSelection] = useState<Selection | null>(
    firstQuestion === undefined ? null : { kind: "question", question: firstQuestion },
  );

  const [view, setView] = useState<View>("top");

  if (selection === null) {
    return null;
  }

  return (
    <div className="plumb-stage">
      <ViewSwitch onView={setView} view={view} />
      <PlanStage
        onRoom={(index, room) => {
          setSelection({ index, kind: "room", room });
        }}
        selection={selection}
        view={view}
      />
      <DemoCard
        onAsk={(question) => {
          setSelection({ kind: "question", question });
        }}
        selection={selection}
      />
    </div>
  );
};
