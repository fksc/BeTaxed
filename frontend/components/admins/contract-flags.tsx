"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { applyContractDocument, listContractFlags } from "@/lib/api/workspace-client";
import type { MismatchFlag } from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";

export function ContractFlagsPage() {
  const t = useTranslations("admins");
  const [rows, setRows] = useState<MismatchFlag[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("flags.needAuth"));
      return;
    }
    const flags = await listContractFlags({ idToken });
    setRows(flags);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("flags.needAuth")));
  }, [t]);

  async function onApply(id: string) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(id);
    try {
      await applyContractDocument(id, { idToken });
      await reload();
    } catch {
      setError(t("flags.applyFailed"));
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <ShellAppBar crumb={t("flags.crumb")} />
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("flags.title")}</div>
        <p className="text-sm text-muted-foreground">{t("flags.lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("flags.empty")}</p>
        ) : (
          rows.map((row) => (
            <Card key={row.id}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">
                  {row.display_name || t("flags.unnamed")} · {row.company_name}
                </CardTitle>
                <CardDescription className="text-xs">{row.filename}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <p>
                  {t("flags.ss")}: {row.ss_modality} / {row.ss_started_on ?? "—"}
                </p>
                <p>
                  {t("flags.paper")}: {row.doc_kind} / {row.signed_on ?? "—"}
                  {row.term_end_on ? ` → ${row.term_end_on}` : ""}
                </p>
                {row.ops_confirmed_at ? (
                  <p className="text-xs text-muted-foreground">{t("flags.applied")}</p>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    disabled={busy === row.id}
                    onClick={() => void onApply(row.id)}
                  >
                    {t("flags.apply")}
                  </Button>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </>
  );
}
