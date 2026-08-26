"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { getMe, listCompanyInvoices } from "@/lib/api/workspace-client";
import type { CompanyInvoiceOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

export function CompaniesInvoicesPage() {
  const t = useTranslations("workspace.invoices");
  const [rows, setRows] = useState<CompanyInvoiceOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      const companyId = loadCompanyId();
      if (!idToken || !companyId) {
        setError(t("needAuth"));
        return;
      }
      try {
        const me = await getMe({ idToken });
        const membership = me.memberships.find((row) => row.company_id === companyId);
        const allowed =
          me.user_type === "BETAXED_STAFF" ||
          membership?.role === "ADMIN" ||
          membership?.role === "FINANCE";
        if (!allowed) {
          setError(t("forbidden"));
          setRows([]);
          return;
        }
        const invoices = await listCompanyInvoices({ idToken, companyId });
        setRows(invoices);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 403) {
          setError(t("forbidden"));
          return;
        }
        setError(t("needAuth"));
      }
    })();
  }, [t]);

  return (
    <>
      <ShellAppBar crumb={t("crumb")} />
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("title")}</CardTitle>
            <CardDescription className="text-xs">{t("lead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            ) : (
              rows.map((row) => (
                <div key={row.id} className="border-b border-border/60 py-2 last:border-0">
                  <div className="text-sm font-medium">
                    {row.lines[0]?.description || row.period_from} · {row.status}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {row.currency} {row.total}
                    {row.issued_on ? ` · ${t("issued")} ${row.issued_on}` : ""}
                    {row.due_on ? ` · ${t("due")} ${row.due_on}` : ""}
                    {row.paid_on ? ` · ${t("paid")} ${row.paid_on}` : ""}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
