"use client";

import { useTranslations } from "next-intl";

import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function SettingsStub({
  crumb,
  title,
  lead,
}: {
  crumb: string;
  title: string;
  lead: string;
}) {
  return (
    <>
      <ShellAppBar crumb={crumb} />
      <div className="p-4 sm:p-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{title}</CardTitle>
            <CardDescription className="text-xs">{lead}</CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </div>
    </>
  );
}

export function CompaniesSettingsPage() {
  const t = useTranslations("workspace.settings");
  return <SettingsStub crumb={t("crumb")} title={t("title")} lead={t("lead")} />;
}

export function AdminsSettingsPage() {
  const t = useTranslations("admins.settings");
  return <SettingsStub crumb={t("crumb")} title={t("title")} lead={t("lead")} />;
}
