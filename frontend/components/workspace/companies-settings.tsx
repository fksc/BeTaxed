"use client";

import { useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";

import { Dropzone } from "@/components/intake/dropzone";
import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DatePicker } from "@/components/ui/date-picker";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { StatusDot, certTone } from "@/components/workspace/status-dot";
import { getMe, listCertificates, listMembers, uploadCertificate } from "@/lib/api/workspace-client";
import type { CertificateOut, MembersBundleOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";
import { MembersPanel } from "@/components/workspace/members-panel";

const PDF_ACCEPT = "application/pdf,.pdf";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function CompaniesSettingsPage() {
  const t = useTranslations("workspace.settings");
  const locale = useLocale();
  const [rows, setRows] = useState<CertificateOut[]>([]);
  const [members, setMembers] = useState<MembersBundleOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"SS_NO_DEBT" | "AT_NO_DEBT" | null>(null);
  const [canUpload, setCanUpload] = useState(false);
  const [canInvite, setCanInvite] = useState(false);
  const [idToken, setIdToken] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [ssIssuedOn, setSsIssuedOn] = useState(todayIso);
  const [atIssuedOn, setAtIssuedOn] = useState(todayIso);
  const [ssFiles, setSsFiles] = useState<File[]>([]);
  const [atFiles, setAtFiles] = useState<File[]>([]);

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("lead"));
      return;
    }
    setIdToken(idToken);
    setCompanyId(companyId);
    try {
      const me = await getMe({ idToken });
      const membership = me.memberships.find((row) => row.company_id === companyId);
      const allowed =
        me.user_type === "BETAXED_STAFF" ||
        membership?.role === "ADMIN" ||
        membership?.role === "FINANCE";
      setCanUpload(allowed);
      setCanInvite(me.user_type === "BETAXED_STAFF" || membership?.role === "ADMIN");
      if (allowed) {
        setRows(await listCertificates({ idToken, companyId }));
      } else {
        setRows([]);
      }
      const bundle = await listMembers({ idToken, companyId });
      setMembers(bundle);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setCanUpload(false);
        setRows([]);
        setError(t("forbidden"));
        return;
      }
      setError(t("lead"));
    }
  }

  useEffect(() => {
    void reload().catch(() => setError(t("lead")));
  }, [t]);

  async function onUpload(kind: "SS_NO_DEBT" | "AT_NO_DEBT") {
    const file = (kind === "SS_NO_DEBT" ? ssFiles[0] : atFiles[0]) ?? undefined;
    const issuedOn = kind === "SS_NO_DEBT" ? ssIssuedOn : atIssuedOn;
    if (!file) {
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusy(kind);
    try {
      await uploadCertificate(kind, issuedOn, file, { idToken, companyId });
      if (kind === "SS_NO_DEBT") {
        setSsFiles([]);
      } else {
        setAtFiles([]);
      }
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("forbidden"));
      } else {
        setError(t("uploadFailed"));
      }
    } finally {
      setBusy(null);
    }
  }

  function caption(until: string): string {
    const tone = certTone(until);
    const date = new Date(`${until}T00:00:00`).toLocaleDateString(
      locale === "pt" ? "pt-PT" : "en-GB",
    );
    if (tone === "bad") {
      return t("statusBad");
    }
    return t(tone === "warn" ? "statusWarn" : "statusOk", { date });
  }

  const latestSs = rows.find((row) => row.kind === "SS_NO_DEBT");
  const latestAt = rows.find((row) => row.kind === "AT_NO_DEBT");

  return (
    <ShellPage crumb={t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("certsTitle")}</CardTitle>
            <CardDescription className="text-xs">{t("certsHint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-1">
            <div className="flex flex-wrap gap-6">
              <StatusDot
                tone={certTone(latestSs?.valid_until)}
                label={`${t("ss")} — ${latestSs ? caption(latestSs.valid_until) : t("statusBad")}`}
              />
              <StatusDot
                tone={certTone(latestAt?.valid_until)}
                label={`${t("at")} — ${latestAt ? caption(latestAt.valid_until) : t("statusBad")}`}
              />
            </div>
            {canUpload ? (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-3">
                  <Dropzone
                    files={ssFiles}
                    disabled={busy !== null}
                    multiple={false}
                    accept={PDF_ACCEPT}
                    title={t("ssDrop")}
                    hint={t("ssDropHint")}
                    onFiles={setSsFiles}
                  />
                  <Field label={t("issuedOn")}>
                    <DatePicker value={ssIssuedOn} onChange={setSsIssuedOn} />
                  </Field>
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy !== null || ssFiles.length === 0}
                    onClick={() => void onUpload("SS_NO_DEBT")}
                  >
                    {t("upload")}
                  </Button>
                </div>
                <div className="space-y-3">
                  <Dropzone
                    files={atFiles}
                    disabled={busy !== null}
                    multiple={false}
                    accept={PDF_ACCEPT}
                    title={t("atDrop")}
                    hint={t("atDropHint")}
                    onFiles={setAtFiles}
                  />
                  <Field label={t("issuedOn")}>
                    <DatePicker value={atIssuedOn} onChange={setAtIssuedOn} />
                  </Field>
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy !== null || atFiles.length === 0}
                    onClick={() => void onUpload("AT_NO_DEBT")}
                  >
                    {t("upload")}
                  </Button>
                </div>
              </div>
            ) : null}
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            ) : (
              rows.map((row) => (
                <div key={row.id} className="text-sm text-muted-foreground">
                  {row.kind === "SS_NO_DEBT" ? t("ss") : t("at")} · {row.issued_on} → {row.valid_until}
                </div>
              ))
            )}
          </CardContent>
        </Card>
        {members && idToken && companyId ? (
          <MembersPanel
            members={members.members}
            invites={members.invites}
            seatsUsed={members.seats_used}
            maxMembers={members.max_members}
            canInvite={canInvite}
            opts={{ idToken, companyId }}
            onChanged={reload}
          />
        ) : null}
      </div>
    </ShellPage>
  );
}
