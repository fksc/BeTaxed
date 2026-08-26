"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { listOpsCompanies } from "@/lib/api/workspace-client";
import type { OpsCompanyListOut } from "@/lib/api/workspace";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";

export function OpsCompaniesPage() {
  const t = useTranslations("admins.companies");
  const [rows, setRows] = useState<OpsCompanyListOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        setError(t("needAuth"));
        return;
      }
      try {
        setRows(await listOpsCompanies({ idToken }));
        setError(null);
      } catch {
        setError(t("needAuth"));
      }
    })();
  }, [t]);

  return (
    <>
      <ShellAppBar crumb={t("crumb")} />
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3 sm:px-6">
        <div>
          <div className="text-base font-semibold">{t("title")}</div>
          <p className="text-sm text-muted-foreground">{t("lead")}</p>
        </div>
        <Button size="sm" render={<Link href={paths.adminsCompanyNew} />}>
          {t("new")}
        </Button>
      </div>
      <div className="space-y-3 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("empty")}</p>
        ) : (
          rows.map((row) => (
            <Card key={row.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">
                  <Link href={paths.adminsCompany(row.id)} className="underline-offset-4 hover:underline">
                    {row.legal_name}
                  </Link>
                </CardTitle>
                <CardDescription className="text-xs">
                  {t("seats", { used: row.seats_used, max: row.max_members })}
                  {row.created_from_intake_id ? ` · ${t("fromIntake")}` : ` · ${t("salesLed")}`}
                </CardDescription>
              </CardHeader>
              <CardContent className="pt-1 text-sm text-muted-foreground">
                {row.trading_name ?? t("noTrading")}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </>
  );
}
