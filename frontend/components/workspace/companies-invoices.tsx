"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import {
  collectSepa,
  getBillingSettings,
  getMe,
  listCompanyInvoices,
  startSepaCheckout,
  uploadLegalPdf,
  uploadProforma,
} from "@/lib/api/workspace-client";
import type { BillingSettingsOut, CompanyInvoiceOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

type DraftFields = { legalNumber: string; atcud: string };

export function CompaniesInvoicesPage() {
  const t = useTranslations("workspace.invoices");
  const [rows, setRows] = useState<CompanyInvoiceOut[]>([]);
  const [billing, setBilling] = useState<BillingSettingsOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, DraftFields>>({});
  const [targetId, setTargetId] = useState<string | null>(null);
  const legalRef = useRef<HTMLInputElement>(null);
  const proformaRef = useRef<HTMLInputElement>(null);

  function draftFor(id: string): DraftFields {
    return drafts[id] ?? { legalNumber: "", atcud: "" };
  }

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("needAuth"));
      return;
    }
    const me = await getMe({ idToken });
    const membership = me.memberships.find((row) => row.company_id === companyId);
    const allowed =
      me.user_type === "BETAXED_STAFF" ||
      membership?.role === "ADMIN" ||
      membership?.role === "FINANCE";
    if (!allowed) {
      setError(t("forbidden"));
      setRows([]);
      return;
    }
    const invoices = await listCompanyInvoices({ idToken, companyId });
    const settings = await getBillingSettings({ idToken, companyId });
    setRows(invoices);
    setBilling(settings);
    setError(null);
  }

  useEffect(() => {
    void reload().catch((err) => {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("forbidden"));
        return;
      }
      setError(t("needAuth"));
    });
  }, [t]);

  async function onLegal(file: File | undefined) {
    if (!file || !targetId) {
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    const draft = draftFor(targetId);
    try {
      await uploadLegalPdf(
        targetId,
        file,
        { legalNumber: draft.legalNumber, atcud: draft.atcud },
        { idToken, companyId },
      );
      await reload();
    } catch {
      setError(t("attachFailed"));
    }
  }

  async function onProforma(file: File | undefined) {
    if (!file || !targetId) {
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    try {
      await uploadProforma(targetId, file, { idToken, companyId });
      await reload();
    } catch {
      setError(t("attachFailed"));
    }
  }

  async function onSepaSetup() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    try {
      const checkout = await startSepaCheckout({ idToken, companyId });
      window.location.assign(checkout.url);
    } catch {
      setError(t("sepaFailed"));
    }
  }

  async function onSepaCollect(invoiceId: string) {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    try {
      await collectSepa(invoiceId, { idToken, companyId });
      await reload();
    } catch {
      setError(t("sepaFailed"));
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
            <CardTitle className="text-sm">{t("sepaSetup")}</CardTitle>
            <CardDescription className="text-xs">
              {billing?.invoicing_method === "STRIPE_SEPA" && billing.has_stripe_customer
                ? t("sepaReady")
                : t("lead")}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-1">
            <Button type="button" size="sm" variant="outline" onClick={() => void onSepaSetup()}>
              {t("sepaSetup")}
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("title")}</CardTitle>
            <CardDescription className="text-xs">{t("lead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("empty")}</p>
            ) : (
              rows.map((row) => {
                const draft = draftFor(row.id);
                return (
                  <div key={row.id} className="border-b border-border/60 py-2 last:border-0">
                    <div className="text-sm font-medium">
                      {row.legal_invoice_number || row.lines[0]?.description || row.period_from} ·{" "}
                      {row.status}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {row.currency} {row.total}
                      {row.issued_on ? ` · ${t("issued")} ${row.issued_on}` : ""}
                      {row.due_on ? ` · ${t("due")} ${row.due_on}` : ""}
                      {row.paid_on ? ` · ${t("paid")} ${row.paid_on}` : ""}
                      {row.atcud ? ` · ${t("atcud")} ${row.atcud}` : ""}
                      {row.has_proforma ? ` · ${t("proforma")}` : ""}
                      {row.has_legal_pdf ? ` · ${t("legalPdf")}` : ""}
                    </div>
                    <div className="mt-2 flex flex-wrap items-end gap-2">
                      <label className="text-xs">
                        {t("legalNumber")}
                        <Input
                          className="mt-1"
                          value={draft.legalNumber}
                          onChange={(event) =>
                            setDrafts((current) => ({
                              ...current,
                              [row.id]: { ...draftFor(row.id), legalNumber: event.target.value },
                            }))
                          }
                        />
                      </label>
                      <label className="text-xs">
                        {t("atcud")}
                        <Input
                          className="mt-1"
                          value={draft.atcud}
                          onChange={(event) =>
                            setDrafts((current) => ({
                              ...current,
                              [row.id]: { ...draftFor(row.id), atcud: event.target.value },
                            }))
                          }
                        />
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setTargetId(row.id);
                          proformaRef.current?.click();
                        }}
                      >
                        {t("proforma")}
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        onClick={() => {
                          setTargetId(row.id);
                          legalRef.current?.click();
                        }}
                      >
                        {t("attachLegal")}
                      </Button>
                      {row.status === "ISSUED" || row.status === "DUE" || row.status === "LATE" ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => void onSepaCollect(row.id)}
                        >
                          {t("sepaCollect")}
                        </Button>
                      ) : null}
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
        <input
          ref={legalRef}
          type="file"
          className="sr-only"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void onLegal(file);
          }}
        />
        <input
          ref={proformaRef}
          type="file"
          className="sr-only"
          accept="application/pdf,.pdf"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void onProforma(file);
          }}
        />
      </div>
    </>
  );
}
