"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

export function MinutaPreviewDialog({
  open,
  title,
  loading,
  error,
  pdfUrl,
  loadingLabel,
  saveLabel,
  backLabel,
  saveDisabled,
  onSave,
  onBack,
}: {
  open: boolean;
  title: string;
  loading: boolean;
  error: string | null;
  pdfUrl: string | null;
  loadingLabel: string;
  saveLabel: string;
  backLabel: string;
  saveDisabled: boolean;
  onSave: () => void;
  onBack: () => void;
}) {
  useEffect(() => {
    if (!open) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onBack();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onBack]);

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        type="button"
        aria-label={backLabel}
        className="absolute inset-0 bg-black/40"
        onClick={onBack}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative flex max-h-[92vh] w-[calc(100%-1rem)] max-w-4xl flex-col overflow-hidden rounded-xl border border-border bg-popover shadow-lg"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
          <div className="text-sm font-semibold">{title}</div>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={onBack}>
              {backLabel}
            </Button>
            <Button type="button" size="sm" disabled={saveDisabled} onClick={onSave}>
              {saveLabel}
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 bg-muted/30 p-4">
          <div className="h-[min(75vh,760px)] overflow-hidden rounded-lg border bg-white">
            {loading ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                <Loader2 className="mr-2 size-4 animate-spin" />
                {loadingLabel}
              </div>
            ) : error ? (
              <div className="flex h-full items-center justify-center px-4 text-center text-sm text-destructive">
                {error}
              </div>
            ) : pdfUrl ? (
              <iframe title={title} src={pdfUrl} className="h-full w-full bg-white" />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
