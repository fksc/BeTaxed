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
    <div className="mb-8 flex items-center justify-between gap-4">
      <a
        href={marketingHomeUrl(locale)}
        className={`inline-flex items-center gap-3 rounded-full py-1.5 pr-5 pl-1.5 text-foreground transition-colors hover:bg-white/16 ${GLASS}`}
      >
        <span className="grid size-10 place-items-center overflow-hidden rounded-full bg-[#f4f1ec]">
          <AnteaterMark className="size-7" />
        </span>
        <span className="font-editorial text-lg tracking-tight">{t("backHome")}</span>
      </a>
      <LocaleSwitcher appearance="glass" />
    </div>
  );
}
