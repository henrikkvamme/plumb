import { Predicate } from "effect";
import type { Schema } from "effect";
import { useState } from "react";

import { numberLabel } from "./format.ts";

type Json = Schema.Json;

type JsonObject = Readonly<Record<string, Json>>;

const isObject = (value: Json): value is JsonObject =>
  Predicate.isObject(value) && !Array.isArray(value);

const isScalar = (value: Json): value is string | number | boolean | null =>
  value === null || !Predicate.isObject(value);

const cellText = (value: Json | undefined): string => {
  if (value === undefined || value === null) {
    return "";
  }

  if (Predicate.isNumber(value)) {
    return numberLabel(value);
  }

  if (Predicate.isBoolean(value)) {
    return value ? "yes" : "no";
  }

  if (Predicate.isString(value)) {
    return value;
  }

  if (Array.isArray(value) && value.every(isScalar)) {
    return value.map((item) => cellText(item)).join(", ");
  }

  return JSON.stringify(value);
};

const heading = (key: string): string => key.replaceAll("_", " ");

const longText = 90;

const firstRows = 8;

export interface DataLinks {
  readonly hotIds: ReadonlySet<string>;
  readonly links: ReadonlyMap<string, readonly string[]>;
  readonly onHover: (ids: readonly string[] | null) => void;
  readonly onSelect: (id: string) => void;
}

interface TableProps {
  readonly links: DataLinks;
  readonly path: string;
  readonly rows: readonly JsonObject[];
}

const Table = ({ links, path, rows }: TableProps) => {
  const [all, setAll] = useState(false);

  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))].filter((column) =>
    rows.some((row) => row[column] !== null && row[column] !== undefined),
  );

  const shown = all ? rows : rows.slice(0, firstRows);

  return (
    <div className="overflow-x-auto">
      <table className="desk-table w-full">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                className={rows.some((row) => Predicate.isNumber(row[column])) ? "text-right" : ""}
                key={column}
              >
                {heading(column)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, index) => {
            const ids = links.links.get(`${path}[${String(index)}]`) ?? [];
            const hot = ids.some((id) => links.hotIds.has(id));
            const [first] = ids;

            return (
              <tr
                className={hot ? "desk-row-hot" : ""}
                data-linked={ids.length > 0}
                key={`${path}[${String(index)}]`}
                onClick={() => {
                  if (first !== undefined) {
                    links.onSelect(first);
                  }
                }}
                onPointerEnter={() => {
                  links.onHover(ids.length > 0 ? ids : null);
                }}
                onPointerLeave={() => {
                  links.onHover(null);
                }}
              >
                {columns.map((column) => (
                  <td
                    className={
                      Predicate.isNumber(row[column]) ? "text-right tabular-nums" : "text-left"
                    }
                    key={column}
                  >
                    {row[column] === null || row[column] === undefined ? (
                      <span className="desk-dash">–</span>
                    ) : (
                      cellText(row[column])
                    )}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length > firstRows ? (
        <button
          className="desk-more"
          onClick={() => {
            setAll((value) => !value);
          }}
          type="button"
        >
          {all ? "Show fewer" : `Show all ${String(rows.length)} rows`}
        </button>
      ) : null}
    </div>
  );
};

interface DataViewProps {
  readonly links: DataLinks;
  readonly path?: string;
  readonly value: Json;
}

export const DataView = ({ links, path = "", value }: DataViewProps) => {
  if (Array.isArray(value)) {
    const rows = value.filter(isObject);

    return rows.length === value.length && rows.length > 0 ? (
      <Table links={links} path={path} rows={rows} />
    ) : (
      <p className="desk-fine break-words">{cellText(value)}</p>
    );
  }

  if (!isObject(value)) {
    return <p className="desk-fine break-words">{cellText(value)}</p>;
  }

  const entries = Object.entries(value);

  const short = entries.filter(
    ([, item]) => isScalar(item) && cellText(item).length <= longText && item !== null,
  );

  const notes = entries.filter(([, item]) => Predicate.isString(item) && item.length > longText);
  const nested = entries.filter(([, item]) => !isScalar(item));

  return (
    <div className="flex flex-col gap-2">
      {short.length > 0 ? (
        <dl className="desk-pairs">
          {short.map(([key, item]) => (
            <div key={key}>
              <dt>{heading(key)}</dt>
              <dd className={Predicate.isNumber(item) ? "tabular-nums" : ""}>{cellText(item)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {nested.map(([key, item]) => (
        <div className="flex flex-col gap-1" key={key}>
          {entries.length > 1 ? <p className="desk-fine">{heading(key)}</p> : null}
          <DataView links={links} path={path === "" ? key : `${path}.${key}`} value={item} />
        </div>
      ))}
      {notes.map(([key, item]) => (
        <p className="desk-fine" key={key}>
          {cellText(item)}
        </p>
      ))}
    </div>
  );
};
