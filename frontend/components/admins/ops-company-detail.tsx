"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { MembersPanel } from "@/components/workspace/members-panel";
import { getOpsCompany, patchOpsCompany } from "@/lib/api/workspace-client";
import type { OpsCompanyDetailOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";

export function OpsCompanyDetailPage({ companyId }: { companyId: string }) {
  const t = useTranslations("admins.companyDetail");
  const tm = useTranslations("members");
  const [row, setRow] = useState<OpsCompanyDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [maxMembers, setMaxMembers] = useState("3");
  const [busy, setBusy] = useState(false);
  const [idToken, setIdToken] = useState<string | null>(null);

  async function reload() {
    const token = await currentIdToken();
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setIdToken(token);
    const detail = await getOpsCompany(companyId, { idToken: token });
    setRow(detail);
    setMaxMembers(String(detail.max_members));
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needAuth")));
  }, [companyId, t]);

  async function onSaveCap() {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      return;
    }
    const parsed = Number(maxMembers);
    if (!Number.isInteger(parsed) || parsed < 1) {
      setError(t("capInvalid"));
      return;
    }
    setBusy(true);
    try {
      const detail = await patchOpsCompany(companyId, { max_members: parsed }, { idToken: token });
      setRow(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("saveFailed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <ShellAppBar crumb={t("crumb")} />
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <Link href={paths.adminsCompanies} className="text-xs text-muted-foreground underline-offset-4 hover:underline">
          {t("back")}
        </Link>
        <div className="text-base font-semibold">{row?.legal_name ?? t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {row ? (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t("capTitle")}</CardTitle>
                <CardDescription className="text-xs">{t("capHint")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-end gap-2 pt-1">
                <label className="text-xs">
                  {tm("maxMembers")}
                  <Input
                    type="number"
                    min={1}
                    className="mt-1 w-24"
                    value={maxMembers}
                    onChange={(event) => setMaxMembers(event.target.value)}
                  />
                </label>
                <Button type="button" size="sm" disabled={busy} onClick={() => void onSaveCap()}>
                  {t("saveCap")}
                </Button>
              </CardContent>
            </Card>
            {idToken ? (
              <MembersPanel
                members={row.members}
                invites={row.invites}
                seatsUsed={row.seats_used}
                maxMembers={row.max_members}
                canInvite
                opts={{ idToken, companyId }}
                onChanged={reload}
              />
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
