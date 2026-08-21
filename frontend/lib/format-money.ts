const NUMBER_LOCALE: Record<string, string> = {
  pt: "pt-PT",
  en: "en-GB",
};

export function formatEur(
  value: string | number | null | undefined,
  locale = "pt",
): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) {
    return "—";
  }
  const tag = NUMBER_LOCALE[locale] ?? "pt-PT";
  return new Intl.NumberFormat(tag, {
    style: "currency",
    currency: "EUR",
  }).format(amount);
}
