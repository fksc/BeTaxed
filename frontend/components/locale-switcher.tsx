"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { usePathname, useRouter } from "@/i18n/navigation";
import { routing, type AppLocale } from "@/i18n/routing";

const GLASS =
  "size-12 rounded-full border border-white/15 bg-white/10 text-foreground shadow-[0_10px_30px_-16px_rgba(0,0,0,0.7)] backdrop-blur-xl backdrop-saturate-150 hover:bg-white/16";

/** Ghost icon + dropdown, same chrome as TJ theme / font-size header actions. */
export function LocaleSwitcher({ appearance = "ghost" }: { appearance?: "ghost" | "glass" }) {
  const t = useTranslations("locale");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();

  function onChange(next: string) {
    if (!routing.locales.includes(next as AppLocale)) {
      return;
    }
    router.replace(pathname, { locale: next as AppLocale });
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={appearance === "glass" ? GLASS : "size-8"}
            aria-label={t("switchTo")}
          />
        }
      >
        <Languages className={appearance === "glass" ? "size-5" : "size-4"} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-36">
        <DropdownMenuRadioGroup value={locale} onValueChange={onChange}>
          {routing.locales.map((code) => (
            <DropdownMenuRadioItem key={code} value={code}>
              {t(code)}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
