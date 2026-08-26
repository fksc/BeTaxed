"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { FileSpreadsheet, Flag, Users, Wallet } from "lucide-react";

import { StatCard } from "@/components/workspace/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { getIntake } from "@/lib/api/intakes";
import type { IntakeOut } from "@/lib/api/types";
import { currentIdToken } from "@/lib/firebase";
import { formatEur } from "@/lib/format-money";
import { loadIntakeSession, loadWorkspaceName } from "@/lib/intake-session";
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
    const stored = loadIntakeSession();
    if (!stored) {
      setError(t("needSession"));
      return;
    }
    void (async () => {
      try {
        const idToken = await currentIdToken();
        const loaded = await getIntake(stored.intakeId, {
          sessionToken: stored.sessionToken,
          idToken,
        });
        setIntake(loaded);
      } catch {
        setError(t("needSession"));
      }
    })();
  }, [t]);

  const name = companyName || t("fallbackName");

  return (
    <>
      <ShellAppBar crumb={t("breadcrumb")} />

      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3 sm:px-6">
        <div>
          <div className="text-xs text-muted-foreground">
            {name} · {t("breadcrumb")}
          </div>
          <div className="text-base font-semibold">{t("overview")}</div>
        </div>
      </div>

      <div className="space-y-5 p-4 sm:p-6">
        {error ? (
          <p className="text-sm text-destructive">
            {error}{" "}
            <Link href="/start" className="underline">
              {t("backToStart")}
            </Link>
          </p>
        ) : null}

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
            <CardContent className="space-y-2 pt-1 text-sm text-muted-foreground">
              <p>{t("next.people")}</p>
              <p>{t("next.declarations")}</p>
              <p>{t("next.billing")}</p>
              <div className="flex flex-wrap gap-3">
                <Link href={paths.companiesPeople} className="text-primary underline">
                  {t("next.openPeople")}
                </Link>
                <Link href={paths.companiesDeclarations} className="text-primary underline">
                  {t("next.openDeclarations")}
                </Link>
                <Link href={paths.companiesInvoices} className="text-primary underline">
                  {t("next.openBilling")}
                </Link>
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
    </>
  );
}
