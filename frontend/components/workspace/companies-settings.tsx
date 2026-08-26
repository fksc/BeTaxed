"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { getMe, listCertificates, uploadCertificate } from "@/lib/api/workspace-client";
import type { CertificateOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring";

export function CompaniesSettingsPage() {
  const t = useTranslations("workspace.settings");
  const [rows, setRows] = useState<CertificateOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [canUpload, setCanUpload] = useState(false);
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
    const [certs, me] = await Promise.all([
      listCertificates({ idToken, companyId }),
      getMe({ idToken }),
    ]);
    const membership = me.memberships.find((row) => row.company_id === companyId);
    setCanUpload(
      me.user_type === "BETAXED_STAFF" ||
        membership?.role === "ADMIN" ||
        membership?.role === "FINANCE",
    );
    setRows(certs);
    setError(null);
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
            <CardTitle className="text-sm">{t("certsTitle")}</CardTitle>
            <CardDescription className="text-xs">{t("certsHint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {canUpload ? (
              <div className="flex flex-wrap items-end gap-2">
                <label className="text-xs">
                  {t("kind")}
                  <select
                    className={`${selectClass} mt-1 block`}
                    value={kind}
                    onChange={(event) =>
                      setKind(event.target.value as "SS_NO_DEBT" | "AT_NO_DEBT")
                    }
                  >
                    <option value="SS_NO_DEBT">{t("ss")}</option>
                    <option value="AT_NO_DEBT">{t("at")}</option>
                  </select>
                </label>
                <label className="text-xs">
                  {t("issuedOn")}
                  <Input
                    type="date"
                    className="mt-1"
                    value={issuedOn}
                    onChange={(event) => setIssuedOn(event.target.value)}
                  />
                </label>
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
      </div>
    </>
  );
}
