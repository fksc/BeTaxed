"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { getMe, listCertificates, listMembers, uploadCertificate } from "@/lib/api/workspace-client";
import type { CertificateOut, MembersBundleOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";
import { MembersPanel } from "@/components/workspace/members-panel";

export function CompaniesSettingsPage() {
  const t = useTranslations("workspace.settings");
  const [rows, setRows] = useState<CertificateOut[]>([]);
  const [members, setMembers] = useState<MembersBundleOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [canUpload, setCanUpload] = useState(false);
  const [canInvite, setCanInvite] = useState(false);
  const [idToken, setIdToken] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState<string | null>(null);
  const [kind, setKind] = useState<"SS_NO_DEBT" | "AT_NO_DEBT">("SS_NO_DEBT");
  const [issuedOn, setIssuedOn] = useState(() => new Date().toISOString().slice(0, 10));
  const fileRef = useRef<HTMLInputElement>(null);

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
      const certs = allowed ? await listCertificates({ idToken, companyId }) : [];
      setRows(certs);
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

  async function onFile(file: File | undefined) {
    if (!file) {
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusy(true);
    try {
      await uploadCertificate(kind, issuedOn, file, { idToken, companyId });
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("forbidden"));
      } else {
        setError(t("uploadFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

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
          <CardContent className="space-y-3 pt-1">
            {canUpload ? (
              <div className="flex flex-wrap items-end gap-3">
                <Field label={t("kind")} className="w-48">
                  <Select
                    value={kind}
                    onValueChange={(value) =>
                      setKind((value as "SS_NO_DEBT" | "AT_NO_DEBT") ?? "SS_NO_DEBT")
                    }
                    items={{
                      SS_NO_DEBT: t("ss"),
                      AT_NO_DEBT: t("at"),
                    }}
                  >
                    <SelectTrigger aria-label={t("kind")}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="SS_NO_DEBT">{t("ss")}</SelectItem>
                      <SelectItem value="AT_NO_DEBT">{t("at")}</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label={t("issuedOn")} className="w-44">
                  <DatePicker value={issuedOn} onChange={setIssuedOn} />
                </Field>
                <Button
                  type="button"
                  size="sm"
                  disabled={busy}
                  onClick={() => fileRef.current?.click()}
                >
                  {t("upload")}
                </Button>
              </div>
            ) : null}
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            ) : (
              rows.map((row) => (
                <div key={row.id} className="text-sm">
                  {row.kind === "SS_NO_DEBT" ? t("ss") : t("at")} · {row.issued_on} →{" "}
                  {row.valid_until}
                </div>
              ))
            )}
          </CardContent>
        </Card>
        <input
          ref={fileRef}
          type="file"
          className="sr-only"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void onFile(file);
          }}
        />
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
