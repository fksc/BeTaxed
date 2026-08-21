"use client";

import { useLocale, useTranslations } from "next-intl";

import { formatEur } from "@/lib/format-money";
import type { VerbosePerson } from "@/lib/api/types";

export function VerboseTable({ people }: { people: VerbosePerson[] }) {
  const t = useTranslations("verbose");
  const locale = useLocale();

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
          {t("kicker")}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="overflow-x-auto rounded-2xl border border-border bg-card">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <thead className="border-b border-border bg-muted/50 text-muted-foreground">
            <tr>
              <th className="px-4 py-3 font-medium">{t("name")}</th>
              <th className="px-4 py-3 font-medium">{t("age")}</th>
              <th className="px-4 py-3 font-medium">{t("contract")}</th>
              <th className="px-4 py-3 font-medium">{t("how")}</th>
              <th className="px-4 py-3 font-medium">{t("monthly")}</th>
            </tr>
          </thead>
          <tbody>
            {people.map((person, index) => (
              <tr
                key={`${person.name ?? "row"}-${index}`}
                className="border-b border-border last:border-0"
              >
                <td className="px-4 py-3 font-medium">
                  {person.name ?? t("unknown")}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {person.age ?? "—"}
                </td>
                <td className="px-4 py-3">
                  {person.contract_label ?? person.contract}
                </td>
                <td className="px-4 py-3">
                  {t(`howCodes.${person.how_code}`, {
                    months: person.remaining_months ?? 0,
                  })}
                </td>
                <td className="px-4 py-3 tabular-nums">
                  {formatEur(person.monthly_eur, locale)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
