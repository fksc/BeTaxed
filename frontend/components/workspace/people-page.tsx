"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { listPeople, uploadPersonContract } from "@/lib/api/workspace-client";
import type { PersonOut } from "@/lib/api/workspace";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

function statusLabel(status: string | null, t: (key: string) => string): string {
  if (!status) {
    return t("people.noFile");
  }
  if (status === "PENDING") {
    return t("people.pending");
  }
  if (status === "FAILED") {
    return t("people.failed");
  }
  return t("people.received");
}

export function PeoplePage() {
  const t = useTranslations("workspace");
  const [rows, setRows] = useState<PersonOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [targetId, setTargetId] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("needSession"));
      return;
    }
    const people = await listPeople({ idToken, companyId });
    setRows(people);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needSession")));
  }, [t]);

  async function onFile(employeeId: string, file: File | undefined) {
    if (!file) {
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusyId(employeeId);
    try {
      await uploadPersonContract(employeeId, file, { idToken, companyId });
      await reload();
    } catch {
      setError(t("people.uploadFailed"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <ShellAppBar crumb={t("peopleCrumb")} />
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("nav.people")}</div>
        <p className="text-sm text-muted-foreground">{t("people.lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("people.title")}</CardTitle>
            <CardDescription className="text-xs">{t("people.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("people.empty")}</p>
            ) : (
              rows.map((row) => (
                <div
                  key={row.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 py-2 last:border-0"
                >
                  <div>
                    <div className="text-sm font-medium">
                      {row.display_name || t("people.unnamed")}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {statusLabel(row.review_status, t)}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busyId === row.id}
                    onClick={() => {
                      setTargetId(row.id);
                      inputRef.current?.click();
                    }}
                  >
                    {t("people.upload")}
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>
        <input
          ref={inputRef}
          type="file"
          className="sr-only"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (targetId) {
              void onFile(targetId, file);
            }
          }}
        />
      </div>
    </>
  );
}
