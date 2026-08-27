"use client";

import { FileSpreadsheet } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";

type Props = {
  files: File[];
  disabled?: boolean;
  onFiles: (files: File[]) => void;
  title?: string;
  hint?: string;
  multiple?: boolean;
  accept?: string;
  className?: string;
};

export function Dropzone({
  files,
  disabled,
  onFiles,
  title,
  hint,
  multiple = true,
  accept = ".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  className,
}: Props) {
  const t = useTranslations("dropzone");
  const inputRef = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function take(list: FileList | File[] | null) {
    if (!list) {
      return;
    }
    const next = Array.from(list).filter((file) => {
      const name = file.name.toLowerCase();
      const wantsPdf = accept.includes(".pdf") || accept.includes("application/pdf");
      const wantsSheet =
        accept.includes(".xlsx") ||
        accept.includes(".csv") ||
        accept.includes("spreadsheet") ||
        accept.includes("text/csv");
      if (wantsPdf && name.endsWith(".pdf")) {
        return true;
      }
      if (wantsSheet && (name.endsWith(".xlsx") || name.endsWith(".csv"))) {
        return true;
      }
      return false;
    });
    if (next.length) {
      onFiles(multiple ? next : next.slice(0, 1));
    }
  }

  return (
    <div className={className}>
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
          "flex w-full flex-col items-center gap-3 rounded-2xl border-2 border-dashed px-6 py-8 text-center transition-colors",
          over
            ? "border-primary bg-primary/5"
            : "border-border bg-card hover:border-primary/40",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <FileSpreadsheet className="size-8 text-primary" strokeWidth={1.5} />
        <div className="space-y-1">
          <p className="font-medium">{title ?? t("title")}</p>
          <p className="text-sm text-muted-foreground">{hint ?? t("hint")}</p>
        </div>
      </button>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept={accept}
        multiple={multiple}
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
