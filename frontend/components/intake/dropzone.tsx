"use client";

import { FileSpreadsheet } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

type Props = {
  files: File[];
  disabled?: boolean;
  onFiles: (files: File[]) => void;
};

export function Dropzone({ files, disabled, onFiles }: Props) {
  const t = useTranslations("dropzone");
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function take(list: FileList | File[] | null) {
    if (!list) {
      return;
    }
    const next = Array.from(list).filter((file) => {
      const name = file.name.toLowerCase();
      return name.endsWith(".xlsx") || name.endsWith(".csv");
    });
    if (next.length) {
      onFiles(next);
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          take(event.dataTransfer.files);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          over
            ? "border-primary bg-primary/5"
            : "border-border bg-card hover:border-primary/40",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <FileSpreadsheet className="size-8 text-primary" strokeWidth={1.5} />
        <div className="space-y-1">
          <p className="font-medium">{t("title")}</p>
          <p className="text-sm text-muted-foreground">{t("hint")}</p>
        </div>
      </button>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        multiple
        disabled={disabled}
        onChange={(event) => take(event.target.files)}
      />
      {files.length > 0 ? (
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {files.map((file) => (
            <li key={`${file.name}-${file.size}`}>{file.name}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
