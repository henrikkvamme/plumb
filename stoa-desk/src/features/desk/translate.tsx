import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@ui-sdk/react/select";
import { Languages, LoaderCircle } from "lucide-react";
import { useState } from "react";

import { translateDrawing } from "#/api/desk.ts";
import { Language } from "#/domain/desk.ts";
import type { Translation } from "#/domain/desk.ts";

const original = "Original";

const choices = [original, ...Language.literals];

const isLanguage = (value: string): value is Language =>
  Language.literals.some((language) => language === value);

export interface LanguagePickProps {
  readonly documentId: string;
  readonly onTranslated: (translation: Translation | null) => void;
}

export const LanguagePick = ({ documentId, onTranslated }: LanguagePickProps) => {
  const [value, setValue] = useState(original);
  const [state, setState] = useState<"idle" | "busy" | "failed">("idle");

  const pick = async (next: string) => {
    setValue(next);

    if (!isLanguage(next)) {
      setState("idle");
      onTranslated(null);

      return;
    }

    setState("busy");

    const result = await translateDrawing({ data: { documentId, language: next } }).catch(
      () => null,
    );

    if (result?.ok === true) {
      setState("idle");
      onTranslated(result.value);
    } else {
      setState("failed");
      onTranslated(null);
    }
  };

  return (
    <Select
      onValueChange={(next) => {
        void pick(next ?? original);
      }}
      value={value}
    >
      <SelectTrigger
        aria-label="Language of the drawing text"
        className="desk-tag desk-language"
        data-state={state === "failed" ? "unknown" : "known"}
        title={
          state === "failed"
            ? "The translation did not work. Pick the language again."
            : "Translate the text of the drawing"
        }
      >
        {state === "busy" ? (
          <LoaderCircle aria-hidden="true" className="desk-spin" size={12} />
        ) : (
          <Languages aria-hidden="true" size={12} />
        )}
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {choices.map((choice) => (
          <SelectItem key={choice} value={choice}>
            {choice}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
