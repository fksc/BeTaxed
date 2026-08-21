import { defineRouting } from "next-intl/routing";

/** Add a locale here and a matching `messages/{locale}.json`. KB: pt, en, … */
export const routing = defineRouting({
  locales: ["pt", "en"],
  defaultLocale: "pt",
  localePrefix: "as-needed",
});

export type AppLocale = (typeof routing.locales)[number];
