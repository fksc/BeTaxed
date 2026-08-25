"use client";

import { useTranslations } from "next-intl";

import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function SiteFooter() {
  const t = useTranslations("marketing.footer");

  return (
    <footer className="mt-auto border-t border-border">
      <div className="mx-auto grid w-full max-w-5xl gap-8 px-6 py-10 sm:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-2 text-sm text-muted-foreground">
          <p className="font-heading text-base text-foreground">{t("brand")}</p>
          <p>{t("email")}</p>
          <p className="whitespace-pre-line">{t("address")}</p>
        </div>
        <nav className="flex flex-col gap-2 text-sm">
          <Link href={paths.about} className="underline-offset-4 hover:underline">
            {t("about")}
          </Link>
          <Link href={paths.contact} className="underline-offset-4 hover:underline">
            {t("contact")}
          </Link>
          <Link href={paths.start} className="underline-offset-4 hover:underline">
            {t("start")}
          </Link>
          <Link href={paths.privacy} className="underline-offset-4 hover:underline">
            {t("privacy")}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
