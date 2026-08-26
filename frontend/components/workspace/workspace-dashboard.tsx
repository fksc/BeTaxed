"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { FileSpreadsheet, Flag, Users, Wallet } from "lucide-react";

import { StatCard } from "@/components/workspace/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { getIntake } from "@/lib/api/intakes";
import { getMeCompany } from "@/lib/api/workspace-client";
import type { IntakeOut } from "@/lib/api/types";
import { currentIdToken } from "@/lib/firebase";
import { formatEur } from "@/lib/format-money";
import { loadIntakeSession } from "@/lib/intake-session";
import { loadCompanyId, loadWorkspaceName, saveWorkspaceName } from "@/lib/company-session";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function WorkspaceDashboard() {
  const t = useTranslations("workspace");
  const locale = useLocale();
  const [intake, setIntake] = useState<IntakeOut | null>(null);
  const [companyName, setCompanyName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCompanyName(loadWorkspaceName());
    void (async () => {
      const idToken = await currentIdToken();
      const companyId = loadCompanyId();
      if (!idToken || !companyId) {
        setError(t("needSession"));
        return;
      }
      try {
        const scope = await getMeCompany({ idToken, companyId });
        saveWorkspaceName(scope.legal_name);
        setCompanyName(scope.legal_name);
        setError(null);
      } catch {
        setError(t("needSession"));
        return;
      }
      const stored = loadIntakeSession();
      if (!stored) {
        return;
      }
      try {
        setIntake(
          await getIntake(stored.intakeId, {
            sessionToken: stored.sessionToken,
            idToken,
          }),
        );
      } catch {
        /* sales-led tenants have no intake; KPIs stay as dashes */
      }
    })();
  }, [t]);

  const name = companyName || t("fallbackName");

  return (
    <ShellPage crumb={t("breadcrumb")}>
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3 sm:px-6">
        <div>
          <div className="text-xs text-muted-foreground">
            {name} · {t("breadcrumb")}
          </div>
          <div className="text-base font-semibold">{t("overview")}</div>
        </div>
      </div>

      <div className="space-y-5 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label={t("kpi.nowMonthly")}
            value={formatEur(intake?.teaser_now_monthly, locale)}
            hint={t("kpi.nowMonthlyHint")}
            icon={<Wallet size={14} />}
          />
          <StatCard
            label={t("kpi.nowWindow")}
            value={formatEur(intake?.teaser_now_window, locale)}
            hint={t("kpi.nowWindowHint")}
            icon={<Flag size={14} />}
          />
          <StatCard
            label={t("kpi.potentialMonthly")}
            value={formatEur(intake?.teaser_potential_monthly, locale)}
            hint={t("kpi.potentialMonthlyHint")}
            icon={<Users size={14} />}
          />
          <StatCard
            label={t("kpi.potentialWindow")}
            value={formatEur(intake?.teaser_potential_window, locale)}
            hint={t("kpi.potentialWindowHint")}
            icon={<FileSpreadsheet size={14} />}
          />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Card className="sm:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("next.title")}</CardTitle>
              <CardDescription className="text-xs">{t("next.lead")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 pt-1 text-sm text-muted-foreground">
              <p>{t("next.people")}</p>
              <p>{t("next.declarations")}</p>
              <p>{t("next.billing")}</p>
              <div className="flex flex-wrap gap-2 pt-1">
                <Button variant="outline" size="sm" render={<Link href={paths.companiesPeople} />}>
                  <Users />
                  {t("next.openPeople")}
                </Button>
                <Button variant="outline" size="sm" render={<Link href={paths.companiesDeclarations} />}>
                  <FileSpreadsheet />
                  {t("next.openDeclarations")}
                </Button>
                <Button variant="outline" size="sm" render={<Link href={paths.companiesInvoices} />}>
                  <Wallet />
                  {t("next.openBilling")}
                </Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">{t("activity.title")}</CardTitle>
            </CardHeader>
            <CardContent className="pt-1">
              <p className="text-xs text-muted-foreground">{t("activity.empty")}</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </ShellPage>
  );
}
