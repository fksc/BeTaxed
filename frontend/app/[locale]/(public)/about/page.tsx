"use client";

import { useTranslations } from "next-intl";

export default function AboutPage() {
  const t = useTranslations("marketing.about");

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12 lg:py-16">
      <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
        {t("kicker")}
      </p>
      <h1 className="font-editorial text-4xl tracking-tight text-balance sm:text-5xl">
        {t("headline")}
      </h1>
      <div className="max-w-2xl space-y-4 text-base leading-relaxed text-muted-foreground">
        <p>{t("p1")}</p>
        <p>{t("p2")}</p>
        <p>{t("p3")}</p>
      </div>
    </main>
  );
}
