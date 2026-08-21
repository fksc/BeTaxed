"use client";

import { useLocale, useTranslations } from "next-intl";

import type { IntakeOut } from "@/lib/api/types";
import { formatEur } from "@/lib/format-money";

export function TeaserCards({ intake }: { intake: IntakeOut }) {
  const t = useTranslations("teaser");
  const locale = useLocale();
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <TeaserCard
        kicker={t("now")}
        monthly={intake.teaser_now_monthly}
        window={intake.teaser_now_window}
        note={t("nowNote")}
        monthlyLabel={t("monthly")}
        windowLabel={t("window")}
        locale={locale}
      />
      <TeaserCard
        kicker={t("potential")}
        monthly={intake.teaser_potential_monthly}
        window={intake.teaser_potential_window}
        note={t("potentialNote")}
        monthlyLabel={t("monthly")}
        windowLabel={t("window")}
        locale={locale}
      />
    </div>
  );
}

function TeaserCard({
  kicker,
  monthly,
  window,
  note,
  monthlyLabel,
  windowLabel,
  locale,
}: {
  kicker: string;
  monthly: string | number | null;
  window: string | number | null;
  note: string;
  monthlyLabel: string;
  windowLabel: string;
  locale: string;
}) {
  return (
    <article className="rounded-2xl border border-border bg-card p-6 shadow-[0_1px_0_oklch(0.22_0.02_250_/_0.04)]">
      <p className="text-xs font-medium tracking-[0.14em] text-accent uppercase">
        {kicker}
      </p>
      <p className="mt-4 font-heading text-3xl tracking-tight tabular-nums">
        {formatEur(monthly, locale)}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{monthlyLabel}</p>
      <p className="mt-5 font-heading text-2xl tracking-tight tabular-nums">
        {formatEur(window, locale)}
      </p>
      <p className="mt-1 text-sm text-muted-foreground">{windowLabel}</p>
      <p className="mt-4 text-sm leading-relaxed text-muted-foreground">{note}</p>
    </article>
  );
}
