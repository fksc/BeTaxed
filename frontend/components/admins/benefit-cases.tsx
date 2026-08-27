"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { listBenefitCases, submitCompanyApplication } from "@/lib/api/workspace-client";
import type { BenefitCaseOut } from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";

export function BenefitCasesPage() {
  const t = useTranslations("admins");
  const [rows, setRows] = useState<BenefitCaseOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("cases.needAuth"));
      return;
    }
    const cases = await listBenefitCases({ idToken });
    setRows(cases);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("cases.needAuth")));
  }, [t]);

  async function onSubmit(companyId: string) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(companyId);
    try {
      await submitCompanyApplication(companyId, { idToken });
      await reload();
    } catch {
      setError(t("cases.submitFailed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <ShellPage crumb={t("cases.crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("cases.title")}</div>
        <p className="text-sm text-muted-foreground">{t("cases.lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("cases.table")}</CardTitle>
            <CardDescription className="text-xs">{t("cases.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("cases.empty")}</p>
            ) : (
              rows.map((row) => (
                <div
                  key={row.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 py-2 last:border-0"
                >
                  <div>
                    <div className="text-sm font-medium">
                      {row.display_name || t("cases.unnamed")} · {row.company_name}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {row.state}
                      {row.ineligibility_code ? ` · ${row.ineligibility_code}` : ""}
                      {row.remaining_months != null
                        ? ` · ${t("cases.remaining", { count: row.remaining_months })}`
                        : ""}
                    </div>
                  </div>
                  {row.state === "DETECTED" || row.state === "READY" ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy === row.company_id}
                      onClick={() => void onSubmit(row.company_id)}
                    >
                      {t("cases.submit")}
                    </Button>
                  ) : null}
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </ShellPage>
  );
}
