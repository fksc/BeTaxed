"use client";

import { cn } from "@/lib/utils";

export type CertTone = "ok" | "warn" | "bad";

export function certTone(validUntil: string | null | undefined, today = new Date()): CertTone {
  if (!validUntil) {
    return "bad";
  }
  const until = new Date(`${validUntil}T00:00:00`);
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  if (Number.isNaN(until.getTime()) || until < start) {
    return "bad";
  }
  const warn = new Date(start);
  warn.setDate(warn.getDate() + 30);
  if (until <= warn) {
    return "warn";
  }
  return "ok";
}

export function StatusDot({
  tone,
  label,
}: {
  tone: CertTone;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2 text-sm">
      <span
        className={cn(
          "status-dot",
          tone === "ok" && "status-dot-ok",
          tone === "warn" && "status-dot-warn",
          tone === "bad" && "status-dot-bad",
        )}
        aria-hidden
      />
      <span>{label}</span>
    </span>
  );
}
