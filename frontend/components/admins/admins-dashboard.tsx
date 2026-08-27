"use client";

import { Building2, FileInput, Flag } from "lucide-react";
import { useTranslations } from "next-intl";

import { StatCard } from "@/components/workspace/stat-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function AdminsDashboard() {
  const t = useTranslations("admins");

  return (
    <ShellPage crumb={t("breadcrumb")}>
      <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3 sm:px-6">
        <div>
          <div className="text-xs text-muted-foreground">{t("brandHint")}</div>
          <div className="text-base font-semibold">{t("overview")}</div>
        </div>
      </div>

      <div className="space-y-5 p-4 sm:p-6">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatCard
            label={t("kpi.companies")}
            value="—"
            hint={t("kpi.companiesHint")}
            icon={<Building2 size={14} />}
          />
          <StatCard
            label={t("kpi.intakes")}
            value="—"
            hint={t("kpi.intakesHint")}
            icon={<FileInput size={14} />}
          />
          <StatCard
            label={t("kpi.flags")}
            value="—"
            hint={t("kpi.flagsHint")}
            icon={<Flag size={14} />}
          />
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("next.title")}</CardTitle>
            <CardDescription className="text-xs">{t("next.lead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 pt-1 text-sm text-muted-foreground">
            <Link href={paths.adminsCompanies} className="text-primary underline">
              {t("nav.companies")}
            </Link>
            <p>{t("next.intakes")}</p>
            <Link href={paths.adminsFlags} className="text-primary underline">
              {t("nav.flags")}
            </Link>
          </CardContent>
        </Card>
      </div>
    </ShellPage>
  );
}
