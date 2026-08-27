"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { FileSpreadsheet, Flag, Settings, Users, Wallet } from "lucide-react";

import { StatCard } from "@/components/workspace/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { getMeCompany } from "@/lib/api/workspace-client";
import { currentIdToken } from "@/lib/firebase";
import { formatEur } from "@/lib/format-money";
import { loadCompanyId, loadWorkspaceName, saveWorkspaceName } from "@/lib/company-session";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { StatusDot, certTone } from "@/components/workspace/status-dot";
import type { CompanyScopeOut } from "@/lib/api/workspace";

export function WorkspaceDashboard() {
  const t = useTranslations("workspace");
  const ts = useTranslations("workspace.settings");
  const locale = useLocale();
  const [scope, setScope] = useState<CompanyScopeOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      const companyId = loadCompanyId();
      if (!idToken || !companyId) {
        setError(t("needSession"));
        return;
      }
      try {
        const loaded = await getMeCompany({ idToken, companyId });
        saveWorkspaceName(loaded.legal_name);
        setScope(loaded);
        setError(null);
      } catch {
        setError(t("needSession"));
      }
    })();
  }, [t]);

  const name = scope?.legal_name || loadWorkspaceName() || t("fallbackName");
  const hasEstimate = scope?.estimate_now_monthly != null;
  const estimateBadge = hasEstimate && scope?.estimate_unconfirmed ? t("kpi.estimate") : undefined;
  const estimateHint =
    hasEstimate && scope && scope.contracts_missing > 0
      ? `${t("kpi.estimateHint")} ${t("kpi.contractsMissing", { count: String(scope.contracts_missing) })}`
      : undefined;

  function certCaption(until: string | null | undefined): string {
    const tone = certTone(until);
    if (tone === "bad") {
      return ts("statusBad");
    }
    const date = until
      ? new Date(`${until}T00:00:00`).toLocaleDateString(locale === "pt" ? "pt-PT" : "en-GB")
      : "—";
    return ts(tone === "warn" ? "statusWarn" : "statusOk", { date });
  }

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

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("certs.title")}</CardTitle>
            <CardDescription className="text-xs">{t("certs.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap items-center gap-6 pt-1">
            <StatusDot
              tone={certTone(scope?.ss_no_debt_valid_until)}
              label={`${t("certs.ss")} — ${certCaption(scope?.ss_no_debt_valid_until)}`}
            />
            <StatusDot
              tone={certTone(scope?.at_no_debt_valid_until)}
              label={`${t("certs.at")} — ${certCaption(scope?.at_no_debt_valid_until)}`}
            />
            <Button variant="outline" size="sm" render={<Link href={paths.companiesSettings} />}>
              <Settings />
              {t("next.openSettings")}
            </Button>
          </CardContent>
        </Card>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label={t("kpi.nowMonthly")}
            value={formatEur(scope?.estimate_now_monthly, locale)}
            hint={estimateHint ?? t("kpi.nowMonthlyHint")}
            badge={estimateBadge}
            icon={<Wallet size={14} />}
          />
          <StatCard
            label={t("kpi.nowWindow")}
            value={formatEur(scope?.estimate_now_window, locale)}
            hint={estimateHint ?? t("kpi.nowWindowHint")}
            badge={estimateBadge}
            icon={<Flag size={14} />}
          />
          <StatCard
            label={t("kpi.potentialMonthly")}
            value={formatEur(scope?.estimate_potential_monthly, locale)}
            hint={estimateHint ?? t("kpi.potentialMonthlyHint")}
            badge={estimateBadge}
            icon={<Users size={14} />}
          />
          <StatCard
            label={t("kpi.potentialWindow")}
            value={formatEur(scope?.estimate_potential_window, locale)}
            hint={estimateHint ?? t("kpi.potentialWindowHint")}
            badge={estimateBadge}
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
                <Button variant="outline" size="sm" render={<Link href={paths.companiesSettings} />}>
                  <Settings />
                  {t("next.openSettings")}
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
