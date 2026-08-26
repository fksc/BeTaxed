"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import {
  createDraftInvoice,
  issueInvoice,
  listOpsInvoices,
  resolveInvoice,
} from "@/lib/api/workspace-client";
import type { StaffInvoiceOut } from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";

function currentMonthFirst(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

export function OpsInvoicesPage() {
  const t = useTranslations("admins.invoices");
  const [rows, setRows] = useState<StaffInvoiceOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [companyId, setCompanyId] = useState("");
  const [period, setPeriod] = useState(currentMonthFirst);
  const [reason, setReason] = useState("Bank transfer received");

  async function reload() {
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("needAuth"));
      return;
    }
    const invoices = await listOpsInvoices({ idToken });
    setRows(invoices);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needAuth")));
  }, [t]);

  async function onDraft() {
    const idToken = await currentIdToken();
    if (!idToken || !companyId) {
      return;
    }
    setBusy("draft");
    try {
      await createDraftInvoice(companyId, period, { idToken });
      await reload();
    } catch {
      setError(t("draftFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function onIssue(id: string) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(id);
    try {
      await issueInvoice(id, { idToken });
      await reload();
    } catch {
      setError(t("issueFailed"));
    } finally {
      setBusy(null);
    }
  }

  async function onResolve(id: string) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(id);
    try {
      await resolveInvoice(id, reason, { idToken });
      await reload();
    } catch {
      setError(t("resolveFailed"));
    } finally {
      setBusy(null);
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
            <CardTitle className="text-sm">{t("draft")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap items-end gap-2 pt-1">
            <label className="text-xs">
              {t("companyId")}
              <Input
                className="mt-1 w-72"
                value={companyId}
                onChange={(event) => setCompanyId(event.target.value)}
              />
            </label>
            <label className="text-xs">
              {t("period")}
              <Input
                type="date"
                className="mt-1"
                value={period}
                onChange={(event) => setPeriod(event.target.value)}
              />
            </label>
            <Button type="button" size="sm" disabled={busy === "draft"} onClick={() => void onDraft()}>
              {t("draft")}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("title")}</CardTitle>
            <CardDescription className="text-xs">{t("lead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            <label className="block text-xs">
              {t("reason")}
              <Input
                className="mt-1"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            ) : (
              rows.map((row) => (
                <div
                  key={row.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 py-2 last:border-0"
                >
                  <div>
                    <div className="text-sm font-medium">
                      {row.company_id.slice(0, 8)} · {row.status} · {row.total}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {row.period_from} → {row.period_to}
                      {row.lines.some((line) => line.saving_amount != null)
                        ? ` · ${row.lines.length} lines`
                        : ""}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {row.status === "DRAFT" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busy === row.id}
                        onClick={() => void onIssue(row.id)}
                      >
                        {t("issue")}
                      </Button>
                    ) : null}
                    {row.status === "ISSUED" || row.status === "DUE" || row.status === "LATE" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        disabled={busy === row.id}
                        onClick={() => void onResolve(row.id)}
                      >
                        {t("resolve")}
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
