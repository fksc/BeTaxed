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

/** Ghost icon + dropdown, same chrome as TJ theme / font-size header actions. */
export function LocaleSwitcher() {
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
            className="size-8"
            aria-label={t("switchTo")}
          />
        }
      >
        <Languages className="size-4" />
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
