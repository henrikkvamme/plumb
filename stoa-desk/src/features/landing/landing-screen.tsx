import { Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import type { PointerEvent } from "react";

import { BrandMark } from "#/features/desk/brand-mark.tsx";

import { areaOf, estimateMargin, largestArea, rooms, squareMetres } from "./plan.ts";
import type { FactStatus } from "./plan.ts";

const pull = (event: PointerEvent<HTMLAnchorElement>) => {
  const box = event.currentTarget.getBoundingClientRect();

  event.currentTarget.style.setProperty(
    "--mx",
    `${((event.clientX - box.left) / box.width - 0.5) * 10}px`,
  );
  event.currentTarget.style.setProperty(
    "--my",
    `${((event.clientY - box.top) / box.height - 0.5) * 8}px`,
  );
};

const release = (event: PointerEvent<HTMLAnchorElement>) => {
  event.currentTarget.style.setProperty("--mx", "0px");
  event.currentTarget.style.setProperty("--my", "0px");
};

export const OpenButton = ({ size }: { readonly size: "quiet" | "small" | "large" }) => (
  <Link
    className="plumb-open no-underline"
    data-size={size}
    onPointerLeave={release}
    onPointerMove={pull}
    to="/desk"
  >
    <span>Open Plumb</span>
    <ArrowRight className="plumb-open-arrow size-4" />
  </Link>
);

const bath = rooms.find((room) => room.status === "estimated");

const kinds: readonly {
  readonly line: string;
  readonly status: FactStatus;
  readonly title: string;
  readonly value: string | null;
}[] = [
  {
    line: "Measured on the drawing.",
    status: "known",
    title: "Known",
    value: squareMetres(largestArea),
  },
  {
    line: "Derived, with an error margin.",
    status: "estimated",
    title: "Estimated",
    value:
      bath === undefined ? null : `${squareMetres(areaOf(bath))} ± ${estimateMargin.toFixed(1)}`,
  },
  {
    line: "Not on the drawing. Plumb does not guess.",
    status: "unknown",
    title: "Unknown",
    value: null,
  },
];

export const Kinds = () => (
  <section className="plumb-section">
    <h2 className="plumb-heading">Each fact says how sure it is.</h2>
    <ul className="plumb-kinds">
      {kinds.map((kind) => (
        <li className="plumb-kind" data-status={kind.status} key={kind.status}>
          <svg aria-hidden="true" className="plumb-kind-dot" viewBox="0 0 64 64">
            <circle className="plumb-kind-ring" cx="32" cy="32" r="27" />
            <circle className="plumb-kind-fill" cx="32" cy="32" r="27" />
          </svg>
          <h3>{kind.title}</h3>
          <p>{kind.line}</p>
          <p className="plumb-kind-value">{kind.value ?? <span className="plumb-dash" />}</p>
        </li>
      ))}
    </ul>
  </section>
);

const formats = ["PDF", "Scan", "DXF", "IFC"];

export const Close = () => (
  <section className="plumb-section plumb-close">
    <span className="plumb-close-mark">
      <BrandMark />
    </span>
    <h2 className="plumb-heading">Open a drawing.</h2>
    <ul className="plumb-formats">
      {formats.map((format) => (
        <li className="desk-tag" key={format}>
          {format}
        </li>
      ))}
    </ul>
    <OpenButton size="large" />
    <p className="plumb-foot">
      Built at Junction 2026 for the Stoa challenge Make Blueprints Talk.
    </p>
  </section>
);
