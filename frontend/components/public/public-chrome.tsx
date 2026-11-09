"use client";

import { useLocale, useTranslations } from "next-intl";

import { AnteaterMark } from "@/components/brand/anteater-logo";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { marketingHomeUrl } from "@/lib/marketing-url";

const GLASS =
  "border border-white/15 bg-white/10 shadow-[0_10px_30px_-16px_rgba(0,0,0,0.7)] backdrop-blur-xl backdrop-saturate-150";

export function PublicChrome() {
  const t = useTranslations("auth");
  const locale = useLocale();

  return (
    <div className="mb-6 flex items-center justify-between gap-3 sm:mb-8">
      <a
        href={marketingHomeUrl(locale)}
        className={`inline-flex min-w-0 items-center gap-2 rounded-full py-1 pr-3 pl-1 text-foreground transition-colors hover:bg-white/16 sm:gap-3 sm:py-1.5 sm:pr-5 sm:pl-1.5 ${GLASS}`}
      >
        <span className="grid size-9 shrink-0 place-items-center overflow-hidden rounded-full bg-[#f4f1ec] sm:size-10">
          <AnteaterMark className="size-6 sm:size-7" />
        </span>
        <span className="truncate font-editorial text-base tracking-tight sm:text-lg">{t("backHome")}</span>
      </a>
      <LocaleSwitcher appearance="glass" />
    </div>
  );
}
