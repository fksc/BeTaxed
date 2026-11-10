const DEFAULT_ORIGIN = "https://anteater.pt";

/** Marketing site origin, no path. Portuguese is the site root; English is /en. */
export function marketingHomeUrl(locale: string): string {
  const raw = process.env.NEXT_PUBLIC_MARKETING_URL?.trim() || DEFAULT_ORIGIN;
  const origin = raw.replace(/\/+$/, "");
  if (locale === "en") return `${origin}/en`;
  return `${origin}/`;
}
