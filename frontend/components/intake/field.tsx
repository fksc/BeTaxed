import type { ComponentProps, ReactNode } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-2.5 text-sm", className)}>
      <span className="leading-none font-medium">{label}</span>
      {children}
      {hint ? (
        <span className="text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

export function TextInput({
  className,
  ...props
}: ComponentProps<"input">) {
  return <Input className={cn(className)} {...props} />;
}
