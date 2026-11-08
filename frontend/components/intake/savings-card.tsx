"use client";

import { useLocale, useTranslations } from "next-intl";

import Counter from "@/components/Counter";
import type { IntakeOut } from "@/lib/api/types";
import { formatEur } from "@/lib/format-money";

const NUMBER_LOCALE: Record<string, string> = {
  pt: "pt-PT",
  en: "en-GB",
};

function asAmount(value: string | number | null | undefined): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const amount = typeof value === "number" ? value : Number(value);
  return Number.isFinite(amount) ? amount : null;
}

export function SavingsCard({ intake }: { intake: IntakeOut }) {
  const t = useTranslations("result");
  const locale = useLocale();
  const potentialWindow = asAmount(intake.teaser_potential_window);
  const nowWindow = asAmount(intake.teaser_now_window);
  const showPotential = potentialWindow !== null && potentialWindow > 0;
  const windowAmount = showPotential ? potentialWindow : nowWindow;
  const monthly = formatEur(
    showPotential ? intake.teaser_potential_monthly : intake.teaser_now_monthly,
    locale,
  );

  return (
    <article className="relative overflow-hidden rounded-[28px] border border-white/10 bg-[#141014] p-6 sm:p-8">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 70% at 100% 0%, rgba(136,55,92,0.45), transparent 55%)",
        }}
      />
      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <p className="text-muted-foreground">{t("potentialLabel")}</p>
          <p className="flex items-center gap-2 text-muted-foreground">
            <span className="status-dot status-dot-ok" />
            {t("estimate")}
          </p>
        </div>
        <div className="mt-6 min-h-16">
          {windowAmount === null ? (
            <p className="font-editorial text-5xl tracking-tight">—</p>
          ) : (
            <Counter
              value={windowAmount}
              locale={NUMBER_LOCALE[locale] ?? "pt-PT"}
              format={{ style: "currency", currency: "EUR" }}
              fontSize="clamp(2.4rem, 6vw, 3.6rem)"
              fontWeight={600}
              textColor="#f4f1ec"
              duration={0.9}
            />
          )}
        </div>
        <p className="mt-4 text-lg text-muted-foreground">
          {t("perMonth", { amount: monthly })}
        </p>
      </div>
    </article>
  );
}
