"use client";

import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import type { RequestCaseEvent } from "@/lib/api/workspace";

export function CaseHistory({
  events,
  onOpenFile,
  className,
}: {
  events: RequestCaseEvent[];
  onOpenFile?: (fileId: string) => void;
  className?: string;
}) {
  const t = useTranslations("caseHistory");
  const locale = useLocale();
  if (events.length === 0) {
    return null;
  }
  return (
    <ol className={className ?? "space-y-1 border-t border-border pt-2"}>
      {events.map((event) => {
        const fileId =
          typeof event.payload?.file_id === "string" ? event.payload.file_id : null;
        return (
          <li key={event.id} className="text-xs text-muted-foreground">
            <span className="text-foreground">
              {event.from_stage_name
                ? t("moved", { from: event.from_stage_name, to: event.to_stage_name })
                : t("opened", { stage: event.to_stage_name })}
            </span>
            {" · "}
            {new Date(event.at).toLocaleString(locale)}
            {fileId && onOpenFile ? (
              <>
                {" · "}
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="h-auto px-0 text-xs"
                  onClick={() => onOpenFile(fileId)}
                >
                  {t("document")}
                </Button>
              </>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
