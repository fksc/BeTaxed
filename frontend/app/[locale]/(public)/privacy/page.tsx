"use client";

import { useTranslations } from "next-intl";

export default function PrivacyPage() {
  const t = useTranslations("marketing.privacy");

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12 lg:py-16">
      <h1 className="font-editorial text-4xl tracking-tight text-balance sm:text-5xl">
        {t("headline")}
      </h1>
      <p className="max-w-2xl text-base leading-relaxed text-muted-foreground">{t("lead")}</p>
    </main>
  );
}
