"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { CaseHistory } from "@/components/case-history";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShellPage } from "@/components/shell/shell-app-bar";
import {
  listCompanyRequestCases,
  openRequestNotice,
  openSentMinuta,
  uploadSignedScan,
} from "@/lib/api/workspace-client";
import type { RequestCaseOut } from "@/lib/api/workspace";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

export function CompanyRequestsPage() {
  const t = useTranslations("workspace.requests");
  const [rows, setRows] = useState<RequestCaseOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("needAuth"));
      return;
    }
    const cases = await listCompanyRequestCases({ idToken, companyId });
    setRows(cases);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needAuth")));
  }, [t]);

  async function onUpload(caseId: string, file: File) {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusyId(caseId);
    try {
      await uploadSignedScan(caseId, file, { idToken, companyId });
      await reload();
    } catch {
      setError(t("uploadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <ShellPage crumb={t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="space-y-3 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("empty")}</p>
        ) : (
          rows.map((row) => (
            <div key={row.id} className="rounded-md border border-border p-3">
              <div className="text-sm font-medium">{row.display_name || row.company_name}</div>
              <div className="text-xs text-muted-foreground">{row.stage_name}</div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {row.minuta_sent ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      void (async () => {
                        const idToken = await currentIdToken();
                        const companyId = loadCompanyId();
                        if (!idToken || !companyId) {
                          return;
                        }
                        await openSentMinuta(row.id, { idToken, companyId });
                      })();
                    }}
                  >
                    {t("downloadMinuta")}
                  </Button>
                ) : null}
                {row.notice_file_id ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const fileId = row.notice_file_id;
                      if (!fileId) {
                        return;
                      }
                      void (async () => {
                        const idToken = await currentIdToken();
                        const companyId = loadCompanyId();
                        if (!idToken || !companyId) {
                          return;
                        }
                        await openRequestNotice(fileId, { idToken, companyId });
                      })();
                    }}
                  >
                    {t("openNotice")}
                  </Button>
                ) : null}
                {row.can_attach_scan ? (
                  <Input
                    type="file"
                    className="max-w-xs"
                    aria-label={t("uploadScan")}
                    disabled={busyId === row.id}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        void onUpload(row.id, file);
                      }
                    }}
                  />
                ) : null}
              </div>
              <div className="mt-2">
                <CaseHistory
                  events={row.events ?? []}
                  onOpenFile={(fileId) => {
                    void (async () => {
                      const idToken = await currentIdToken();
                      const companyId = loadCompanyId();
                      if (!idToken || !companyId) {
                        return;
                      }
                      await openRequestNotice(fileId, { idToken, companyId });
                    })();
                  }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </ShellPage>
  );
}
