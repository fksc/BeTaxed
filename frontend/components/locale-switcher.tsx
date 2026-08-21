"use client";

import { useLocale, useTranslations } from "next-intl";

import { Link, usePathname } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { cn } from "@/lib/utils";

export function LocaleSwitcher() {
  const t = useTranslations("locale");
  const locale = useLocale();
  const pathname = usePathname();

  return (
    <nav aria-label={t("switchTo")} className="flex items-center gap-2 text-sm">
      {routing.locales.map((code) => (
        <Link
          key={code}
          href={pathname}
          locale={code}
          className={cn(
            "underline-offset-4",
            code === locale
              ? "font-medium text-foreground"
              : "text-muted-foreground hover:underline",
          )}
        >
          {t(code)}
        </Link>
      ))}
    </nav>
  );
}
