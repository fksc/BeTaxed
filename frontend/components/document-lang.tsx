"use client";

import { useLocale } from "next-intl";
import { useLayoutEffect } from "react";

/** Root <html lang> is the default locale; keep it in sync after navigation. */
export function DocumentLang() {
  const locale = useLocale();
  useLayoutEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);
  return null;
}
