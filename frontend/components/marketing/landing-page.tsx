"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function LandingPage() {
  const t = useTranslations("marketing.landing");

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-6 py-12 lg:py-16">
      <h1 className="font-heading text-5xl tracking-tight text-balance sm:text-6xl">
        {t("headline")}
      </h1>

      <div
        aria-hidden
        className="relative min-h-[14rem] overflow-hidden rounded-sm bg-primary sm:min-h-[22rem]"
      >
        <div className="absolute inset-0 bg-[linear-gradient(120deg,oklch(0.98_0.01_85_/_0.12),transparent_42%,oklch(0.22_0.03_250_/_0.35))]" />
        <div className="absolute inset-y-8 left-[12%] w-px bg-primary-foreground/20" />
        <div className="absolute inset-y-8 right-[28%] w-px bg-primary-foreground/15" />
        <div className="absolute inset-x-10 bottom-[28%] h-px bg-primary-foreground/15" />
        <p className="absolute right-8 bottom-8 max-w-xs text-right font-heading text-lg italic text-primary-foreground/90">
          {t("heroCaption")}
        </p>
      </div>

      <h2 className="max-w-3xl text-lg font-medium tracking-tight text-balance sm:text-xl">
        {t("subhead")}
      </h2>
      <p className="max-w-2xl text-base leading-relaxed text-muted-foreground">
        {t("lead")}
      </p>
      <div>
        <Button size="lg" render={<Link href={paths.start} />}>
          {t("cta")}
        </Button>
      </div>

      <div className="max-w-2xl space-y-4 text-sm leading-relaxed text-muted-foreground">
        <p>{t("p1")}</p>
        <p>{t("p2")}</p>
        <p>{t("p3")}</p>
      </div>
    </main>
  );
}
