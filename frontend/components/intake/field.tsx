import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

const inputClass =
  "h-11 w-full rounded-xl border border-border bg-card px-3 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint ? (
        <span className="text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </label>
  );
}

export function TextInput({
  className,
  ...props
}: ComponentProps<"input">) {
  return <input className={cn(inputClass, className)} {...props} />;
}
