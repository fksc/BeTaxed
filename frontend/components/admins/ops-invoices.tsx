"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DatePicker } from "@/components/ui/date-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field } from "@/components/intake/field";
import { ShellPage } from "@/components/shell/shell-app-bar";
import {
  createDraftInvoice,
  collectOpsInvoice,
  issueInvoice,
  listOpsInvoices,
  resolveInvoice,
  setCompanyInvoicing,
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
  const [method, setMethod] = useState("CERTIFIED_SOFTWARE");
  const [vendor, setVendor] = useState("");

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

  async function onMethod() {
    const idToken = await currentIdToken();
    if (!idToken || !companyId) {
      return;
    }
    setBusy("method");
    try {
      await setCompanyInvoicing(companyId, method, vendor, { idToken });
      await reload();
    } catch {
      setError(t("methodFailed"));
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

  async function onCollect(id: string) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(id);
    try {
      await collectOpsInvoice(id, { idToken });
      await reload();
    } catch {
      setError(t("collectFailed"));
    } finally {
      setBusy(null);
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
          <CardHeader>
            <CardTitle>{t("draft")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <Field label={t("companyId")}>
              <Input
                className="w-full sm:w-72"
                value={companyId}
                onChange={(event) => setCompanyId(event.target.value)}
              />
            </Field>
            <Field label={t("period")}>
              <DatePicker value={period} onChange={setPeriod} className="sm:w-44" />
            </Field>
            <Button type="button" size="sm" disabled={busy === "draft"} onClick={() => void onDraft()}>
              {t("draft")}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("method")}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-end">
            <Field label={t("method")}>
              <Select
                value={method}
                onValueChange={(value) => setMethod(value ?? "CERTIFIED_SOFTWARE")}
                items={{
                  CERTIFIED_SOFTWARE: t("methodCertified"),
                  STRIPE_SEPA: t("methodSepa"),
                }}
              >
                <SelectTrigger className="w-full sm:w-56">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="CERTIFIED_SOFTWARE">{t("methodCertified")}</SelectItem>
                  <SelectItem value="STRIPE_SEPA">{t("methodSepa")}</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label={t("vendor")}>
              <Input
                className="w-full sm:w-56"
                value={vendor}
                onChange={(event) => setVendor(event.target.value)}
              />
            </Field>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy === "method"}
              onClick={() => void onMethod()}
            >
              {t("saveMethod")}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("title")}</CardTitle>
            <CardDescription>{t("lead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label={t("reason")}>
              <Input
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </Field>
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
                      {row.legal_invoice_number || row.company_id.slice(0, 8)} · {row.status} ·{" "}
                      {row.total}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {row.period_from} → {row.period_to}
                      {row.atcud ? ` · ${t("atcud")} ${row.atcud}` : ""}
                      {row.certified_external_id
                        ? ` · ${t("vendorId")} ${row.certified_external_id}`
                        : ""}
                      {row.has_proforma ? ` · ${t("proforma")}` : ""}
                      {row.has_legal_pdf ? ` · ${t("legalPdf")}` : ""}
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
                      <>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy === row.id}
                          onClick={() => void onCollect(row.id)}
                        >
                          {t("collect")}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={busy === row.id}
                          onClick={() => void onResolve(row.id)}
                        >
                          {t("resolve")}
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>
    </ShellPage>
  );
}
