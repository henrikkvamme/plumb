import { Download, FileUp, Plus, Trash2 } from "lucide-react";
import { Option, Schema } from "effect";
import { useEffect, useRef, useState } from "react";

import type { DrawingDocument } from "#/domain/desk.ts";

type Sample = DrawingDocument["samples"][number];

const accepted = [".png", ".jpg", ".jpeg", ".pdf", ".ifc", ".dxf"];

export const acceptedLabel = "PNG, JPG, PDF, IFC or DXF";

export const isAccepted = (file: File): boolean =>
  accepted.some((extension) => file.name.toLowerCase().endsWith(extension));

const ownKey = "stoa-desk.uploads";

const OwnIds = Schema.fromJsonString(Schema.Array(Schema.String));

const isUpload = (id: string): boolean => id.startsWith("up-");

const isOwn = (sample: Sample): boolean => isUpload(sample.id);

export const ownUploads = (): readonly string[] => {
  try {
    return Option.getOrElse(
      Schema.decodeOption(OwnIds)(globalThis.localStorage.getItem(ownKey) ?? "[]"),
      () => [],
    );
  } catch {
    return [];
  }
};

export const rememberUpload = (id: string): readonly string[] => {
  const known = ownUploads();

  if (!isUpload(id) || known.includes(id)) {
    return known;
  }

  const next = [...known, id].slice(-40);

  try {
    globalThis.localStorage.setItem(ownKey, JSON.stringify(next));
  } catch {
    return next;
  }

  return next;
};

export const isVisible = (id: string, own: readonly string[], open: string): boolean =>
  !isUpload(id) || id === open || own.includes(id);

const Thumb = ({
  current,
  disabled,
  onOpen,
  onRemove,
  sample,
}: {
  readonly current: boolean;
  readonly disabled: boolean;
  readonly onOpen: (id: string) => void;
  readonly onRemove: (id: string) => void;
  readonly sample: Sample;
}) => {
  const [armed, setArmed] = useState(false);

  return (
    <li
      className="desk-thumb-wrap"
      onPointerLeave={() => {
        setArmed(false);
      }}
    >
      <button
        aria-label={`${sample.name}, ${sample.tag}, ${sample.format}`}
        aria-pressed={current}
        className="desk-thumb"
        disabled={disabled}
        onClick={() => {
          onOpen(sample.id);
        }}
        type="button"
      >
        <span className="desk-thumb-picture">
          <img alt="" loading="lazy" src={`/api/sample?id=${sample.id}&part=thumb`} />
        </span>
        <span>
          <span className="desk-thumb-name">{sample.name}</span>
          <span className="desk-fine block truncate">
            {sample.tag} · {sample.format}
          </span>
        </span>
      </button>
      <a
        aria-label={`Download ${sample.name}`}
        className="desk-thumb-save"
        download
        href={`/api/sample?id=${sample.id}&part=file`}
        title="Download this drawing"
      >
        <Download aria-hidden="true" size={12} />
      </a>
      {isOwn(sample) ? (
        <button
          aria-label={armed ? `Confirm: delete ${sample.name}` : `Delete ${sample.name}`}
          className="desk-thumb-remove"
          data-armed={armed}
          onClick={() => {
            if (armed) {
              onRemove(sample.id);
            } else {
              setArmed(true);
            }
          }}
          title={armed ? "Click again to delete" : "Delete this drawing"}
          type="button"
        >
          <Trash2 aria-hidden="true" size={12} />
          {armed ? <span>Delete</span> : null}
        </button>
      ) : null}
    </li>
  );
};

export interface DrawingStripProps {
  readonly currentId: string;
  readonly disabled: boolean;
  readonly onFile: (file: File) => void;
  readonly onOpen: (id: string) => void;
  readonly onRemove: (id: string) => void;
  readonly samples: readonly Sample[];
}

export const DrawingStrip = ({
  currentId,
  disabled,
  onFile,
  onOpen,
  onRemove,
  samples,
}: DrawingStripProps) => {
  const input = useRef<HTMLInputElement>(null);

  return (
    <nav
      aria-label="Drawings"
      onPointerDown={(event) => {
        event.stopPropagation();
      }}
      onWheel={(event) => {
        event.stopPropagation();
      }}
    >
      <ul className="desk-strip">
        <li className="desk-thumb-wrap flex">
          <button
            className="desk-thumb"
            data-add="true"
            disabled={disabled}
            onClick={() => {
              input.current?.click();
            }}
            type="button"
          >
            <Plus aria-hidden="true" size={20} />
            <span className="desk-thumb-name">Add your drawing</span>
            <span className="desk-fine">or drop a file here</span>
          </button>
          <input
            accept={accepted.join(",")}
            className="sr-only"
            onChange={(event) => {
              const [file] = event.target.files ?? [];

              if (file !== undefined) {
                onFile(file);
              }

              event.target.value = "";
            }}
            ref={input}
            tabIndex={-1}
            type="file"
          />
        </li>
        <li className="desk-thumb-wrap flex">
          <a
            className="desk-thumb"
            data-add="true"
            download
            href="/api/sample?id=test-set&part=file"
          >
            <Download aria-hidden="true" size={20} />
            <span className="desk-thumb-name">Test drawings</span>
            <span className="desk-fine">9 files to drop here</span>
          </a>
        </li>
        {samples.map((sample) => (
          <Thumb
            current={sample.id === currentId}
            disabled={disabled}
            key={sample.id}
            onOpen={onOpen}
            onRemove={onRemove}
            sample={sample}
          />
        ))}
      </ul>
    </nav>
  );
};

const carriesFiles = (event: DragEvent): boolean =>
  event.dataTransfer?.types.includes("Files") ?? false;

export const DropZone = ({ onFile }: { readonly onFile: (file: File) => void }) => {
  const [over, setOver] = useState(false);
  const depth = useRef(0);

  useEffect(() => {
    const enter = (event: DragEvent) => {
      if (carriesFiles(event)) {
        event.preventDefault();
        depth.current += 1;
        setOver(true);
      }
    };

    const leave = (event: DragEvent) => {
      if (carriesFiles(event)) {
        depth.current = Math.max(0, depth.current - 1);
        setOver(depth.current > 0);
      }
    };

    const hold = (event: DragEvent) => {
      if (carriesFiles(event)) {
        event.preventDefault();
      }
    };

    const drop = (event: DragEvent) => {
      if (!carriesFiles(event)) {
        return;
      }

      event.preventDefault();
      depth.current = 0;
      setOver(false);

      const [file] = event.dataTransfer?.files ?? [];

      if (file !== undefined) {
        onFile(file);
      }
    };

    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", hold);
    window.addEventListener("drop", drop);

    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", hold);
      window.removeEventListener("drop", drop);
    };
  }, [onFile]);

  return over ? (
    <div className="desk-drop pointer-events-none fixed inset-0 z-50" data-testid="drop-zone">
      <div>
        <FileUp aria-hidden="true" size={34} />
        <p className="text-xl font-medium">Drop the drawing to read it</p>
        <p className="desk-fine">{acceptedLabel}</p>
      </div>
    </div>
  ) : null;
};
