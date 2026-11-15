import type { PointerEvent } from "react";

import { BrandMark } from "#/features/desk/brand-mark.tsx";

import { Demo } from "./demo.tsx";
import { Close, Kinds, OpenButton } from "./landing-screen.tsx";
import { areaOf, largestArea, pointsOf, rooms, squareMetres, wallPath } from "./plan.ts";

const follow = (event: PointerEvent<HTMLElement>) => {
  const box = event.currentTarget.getBoundingClientRect();

  event.currentTarget.style.setProperty(
    "--px",
    (((event.clientX - box.left) / box.width) * 2 - 1).toFixed(3),
  );
  event.currentTarget.style.setProperty(
    "--py",
    (((event.clientY - box.top) / box.height) * 2 - 1).toFixed(3),
  );
};

const rest = (event: PointerEvent<HTMLElement>) => {
  event.currentTarget.style.setProperty("--px", "0");
  event.currentTarget.style.setProperty("--py", "0");
};

const largest = rooms.find((room) => areaOf(room) === largestArea);

const SheetTag = ({ number, title }: { readonly number: number; readonly title: string }) => (
  <span className="plumb-ltag">
    <span>{number}</span>
    {title}
  </span>
);

const Sheets = () => (
  <div aria-hidden="true" className="plumb-lscene">
    <div className="plumb-liso">
      <span className="plumb-lsheet" data-sheet="shadow" />
      <div className="plumb-lsheet" data-sheet="drawing">
        <svg viewBox="0 0 320 220">
          <path d={wallPath} />
        </svg>
        <SheetTag number={1} title="Drawing" />
      </div>
      <div className="plumb-lsheet" data-sheet="facts">
        <svg viewBox="0 0 320 220">
          {rooms.map((room, index) => (
            <polygon key={room.name} points={pointsOf(room)} style={{ "--i": index }} />
          ))}
          {rooms.map((room) => (
            <g key={room.name}>
              <circle
                cx={room.label[0] - 22}
                cy={room.label[1] - 2.4}
                data-status={room.status}
                r="2.6"
              />
              <text x={room.label[0] - 16} y={room.label[1]}>
                {room.name}
              </text>
              <text className="plumb-larea" x={room.label[0] - 16} y={room.label[1] + 9}>
                {squareMetres(areaOf(room))}
              </text>
            </g>
          ))}
        </svg>
        <SheetTag number={2} title="Facts" />
      </div>
      <div className="plumb-lsheet" data-sheet="answer">
        {largest === undefined ? null : (
          <svg viewBox="0 0 320 220">
            <polygon points={pointsOf(largest)} />
            <g transform={`rotate(40 ${largest.label[0]} ${largest.label[1] - 4})`}>
              <circle cx={largest.label[0]} cy={largest.label[1] - 4} r="15" />
              <path
                d={`M${largest.label[0] - 6} ${largest.label[1] - 4}l4.5 4.5l8-9`}
                pathLength={1}
              />
            </g>
          </svg>
        )}
        <SheetTag number={3} title="Answer" />
      </div>
    </div>
  </div>
);

const Hero = () => (
  <section className="plumb-lhero" onPointerLeave={rest} onPointerMove={follow}>
    <nav className="plumb-nav">
      <span className="plumb-logo">
        <BrandMark />
        Plumb
      </span>
      <OpenButton size="quiet" />
    </nav>
    <Sheets />
    <div className="plumb-lhead">
      <h1 className="plumb-title plumb-ltitle">
        <span>
          <span>Ask a building drawing.</span>
        </span>
        <span>
          <span>Check the answer.</span>
        </span>
      </h1>
      <p className="plumb-lede">Plumb reads floor plans from PDF, scans, DXF and IFC.</p>
      <OpenButton size="large" />
    </div>
  </section>
);

const Try = () => (
  <section className="plumb-section plumb-try">
    <h2 className="plumb-heading">Click a room. Ask a question.</h2>
    <Demo />
  </section>
);

export const LayersScreen = () => (
  <main className="plumb-page">
    <Hero />
    <Try />
    <Kinds />
    <Close />
  </main>
);
