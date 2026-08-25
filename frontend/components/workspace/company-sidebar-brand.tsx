"use client";

import { Building2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { loadWorkspaceName } from "@/lib/intake-session";
import { cn } from "@/lib/utils";

function initialsFromName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function CompanySidebarBrand() {
  const t = useTranslations("workspace");
  const [name, setName] = useState<string | null>(null);

  useEffect(() => {
    setName(loadWorkspaceName());
  }, []);

  const label = name || t("fallbackName");
  const initials = initialsFromName(label);

  return (
    <div className="flex min-w-0 items-center gap-2 px-2 py-1 group-data-[collapsible=icon]:justify-center">
      <div
        className={cn(
          "flex size-8 shrink-0 items-center justify-center overflow-hidden rounded-full border border-sidebar-border bg-primary text-[0.65rem] font-medium text-primary-foreground",
        )}
        aria-hidden
      >
        {name ? initials : <Building2 className="size-4" />}
      </div>
      <div className="min-w-0 group-data-[collapsible=icon]:hidden">
        <p className="truncate text-sm font-medium leading-tight">{label}</p>
        <p className="truncate text-xs text-sidebar-foreground/70">{t("brandHint")}</p>
      </div>
    </div>
  );
}
