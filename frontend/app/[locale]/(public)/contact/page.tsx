"use client";

import { useTranslations } from "next-intl";

export default function ContactPage() {
  const t = useTranslations("marketing.contact");

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-12 lg:py-16">
      <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
        {t("kicker")}
      </p>
      <h1 className="font-heading text-4xl tracking-tight text-balance sm:text-5xl">
        {t("headline")}
      </h1>
      <div className="max-w-xl space-y-2 text-base leading-relaxed text-muted-foreground">
        <p>
          <a
            className="text-foreground underline-offset-4 hover:underline"
            href={`mailto:${t("email")}`}
          >
            {t("email")}
          </a>
        </p>
        <p className="whitespace-pre-line">{t("address")}</p>
      </div>
    </main>
  );
}
