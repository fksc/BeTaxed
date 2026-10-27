"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";

import { MinutaEditor } from "@/components/admins/minuta-editor";
import { Button } from "@/components/ui/button";
import { DatePicker } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listMinutaTokens,
  previewMinutaPdf,
  refreshCaseFacts,
  runRequestOperation,
  saveCaseFacts,
  saveMinutaDraft,
} from "@/lib/api/workspace-client";
import type { MinutaTemplateOut, RequestCaseOut } from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";
import { cn } from "@/lib/utils";

const STEPS = ["facts", "text", "preview"] as const;

function hasBody(html: string): boolean {
  return html.replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim().length > 0;
}

export function MinutaWizard({
  row,
  templates,
  busy,
  onClose,
  onChanged,
}: {
  row: RequestCaseOut;
  templates: MinutaTemplateOut[];
  busy: boolean;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const t = useTranslations("admins.cases");
  const [step, setStep] = useState(0);
  const [templateId, setTemplateId] = useState(templates[0]?.id ?? "");
  const [personAddress, setPersonAddress] = useState(row.person_address ?? "");
  const [personNif, setPersonNif] = useState(row.person_nif ?? "");
  const [personNiss, setPersonNiss] = useState(row.person_niss ?? "");
  const [companyAddress, setCompanyAddress] = useState(row.company_address ?? "");
  const [signatory, setSignatory] = useState(row.company_signatory_name ?? "");
  const [companyNif, setCompanyNif] = useState(row.company_nif ?? "");
  const [companyNiss, setCompanyNiss] = useState(row.company_niss ?? "");
  const [started, setStarted] = useState(row.contract_started_on ?? "");
  const [converted, setConverted] = useState(row.converted_on ?? "");
  const [declared, setDeclared] = useState(row.declared_on ?? "");
  const [place, setPlace] = useState(row.signed_place ?? "");
  const [draft, setDraft] = useState(row.draft_html ?? "");
  const [editorKey, setEditorKey] = useState(0);
  const [tokens, setTokens] = useState<{ key: string }[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    setDraft(row.draft_html ?? "");
    setEditorKey((key) => key + 1);
  }, [row.draft_html]);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        return;
      }
      setTokens(await listMinutaTokens({ idToken }));
    })();
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    setPersonAddress(row.person_address ?? "");
    setPersonNif(row.person_nif ?? "");
    setPersonNiss(row.person_niss ?? "");
    setCompanyAddress(row.company_address ?? "");
    setSignatory(row.company_signatory_name ?? "");
    setCompanyNif(row.company_nif ?? "");
    setCompanyNiss(row.company_niss ?? "");
    setStarted(row.contract_started_on ?? "");
    setConverted(row.converted_on ?? "");
    setDeclared(row.declared_on ?? "");
    setPlace(row.signed_place ?? "");
  }, [
    row.person_address,
    row.person_nif,
    row.person_niss,
    row.company_address,
    row.company_signatory_name,
    row.company_nif,
    row.company_niss,
    row.contract_started_on,
    row.converted_on,
    row.declared_on,
    row.signed_place,
  ]);

  async function persistFacts() {
    const idToken = await currentIdToken();
    if (!idToken) {
      return false;
    }
    await saveCaseFacts(
      row.id,
      {
        person_address: personAddress,
        person_nif: personNif,
        person_niss: personNiss,
        company_address: companyAddress,
        company_signatory_name: signatory,
        company_nif: companyNif,
        company_niss: companyNiss,
        contract_started_on: started,
        converted_on: converted,
        declared_on: declared,
        signed_place: place,
      },
      { idToken },
    );
    return true;
  }

  async function fillFromTemplate() {
    if (!templateId) {
      return;
    }
    setError(null);
    setSending(true);
    try {
      const idToken = await currentIdToken();
      if (!idToken || !(await persistFacts())) {
        return;
      }
      await runRequestOperation(row.id, "GENERATE_MINUTA", { template_id: templateId }, { idToken });
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("actionFailed"));
    } finally {
      setSending(false);
    }
  }

  async function openPreview() {
    const idToken = await currentIdToken();
    setStep(2);
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
    if (!idToken) {
      setPreviewError(t("needAuth"));
      setPreviewLoading(false);
      return;
    }
    try {
      const blob = await previewMinutaPdf(draft, { idToken });
      setPreviewUrl(URL.createObjectURL(blob));
    } catch {
      setPreviewError(t("previewFailed"));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function sendToSignature() {
    setError(null);
    setSending(true);
    try {
      const idToken = await currentIdToken();
      if (!idToken || !(await persistFacts())) {
        return;
      }
      if (row.draft_html) {
        await saveMinutaDraft(row.id, draft, { idToken });
      } else {
        await runRequestOperation(
          row.id,
          "GENERATE_MINUTA",
          { template_id: templateId, body_html: draft },
          { idToken },
        );
      }
      await runRequestOperation(row.id, "SEND_MINUTA", { body_html: draft }, { idToken });
      await onChanged();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("actionFailed"));
    } finally {
      setSending(false);
    }
  }

  const stepLabel = [t("wizardFacts"), t("wizardText"), t("wizardPreview")];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button type="button" aria-label={t("wizardClose")} className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={t("prepareMinuta")}
        className="relative flex max-h-[92vh] w-[calc(100%-1rem)] max-w-5xl flex-col overflow-hidden rounded-xl border border-border bg-popover shadow-lg"
      >
        <div className="border-b px-5 py-4">
          <div className="text-sm font-semibold">{row.display_name || t("unnamed")}</div>
          <div className="mt-3 flex gap-2">
            {STEPS.map((id, index) => (
              <button
                key={id}
                type="button"
                className={cn(
                  "rounded-full px-3 py-1 text-xs",
                  index === step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
                )}
                onClick={() => {
                  if (index === 2) {
                    void openPreview();
                    return;
                  }
                  setStep(index);
                }}
              >
                {index + 1}. {stepLabel[index]}
              </button>
            ))}
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
          {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}
          {step === 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <Input aria-label={t("personAddress")} value={personAddress} placeholder={t("personAddress")} onChange={(event) => setPersonAddress(event.target.value)} />
              <Input aria-label={t("personNif")} value={personNif} placeholder={t("personNif")} onChange={(event) => setPersonNif(event.target.value)} />
              <Input aria-label={t("personNiss")} value={personNiss} placeholder={t("personNiss")} onChange={(event) => setPersonNiss(event.target.value)} />
              <Input aria-label={t("companyAddress")} value={companyAddress} placeholder={t("companyAddress")} onChange={(event) => setCompanyAddress(event.target.value)} />
              <Input aria-label={t("signatory")} value={signatory} placeholder={t("signatory")} onChange={(event) => setSignatory(event.target.value)} />
              <Input aria-label={t("companyNif")} value={companyNif} placeholder={t("companyNif")} onChange={(event) => setCompanyNif(event.target.value)} />
              <Input aria-label={t("companyNiss")} value={companyNiss} placeholder={t("companyNiss")} onChange={(event) => setCompanyNiss(event.target.value)} />
              <Input aria-label={t("signedPlace")} value={place} placeholder={t("signedPlace")} onChange={(event) => setPlace(event.target.value)} />
              <DatePicker value={started} aria-label={t("contractStart")} onChange={setStarted} />
              <DatePicker value={converted} aria-label={t("convertedOn")} onChange={setConverted} />
              <DatePicker value={declared} aria-label={t("declaredOn")} onChange={setDeclared} />
              <div className="sm:col-span-2">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy || sending}
                  onClick={() => {
                    void (async () => {
                      const idToken = await currentIdToken();
                      if (!idToken) {
                        return;
                      }
                      await refreshCaseFacts(row.id, { idToken });
                      await onChanged();
                    })();
                  }}
                >
                  {t("refreshFacts")}
                </Button>
              </div>
            </div>
          ) : null}
          {step === 1 ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-end gap-2">
                <Select
                  value={templateId}
                  items={Object.fromEntries(templates.map((template) => [template.id, template.title]))}
                  onValueChange={(value) => value && setTemplateId(value)}
                >
                  <SelectTrigger className="w-64" aria-label={t("minuta")}>
                    <SelectValue placeholder={t("minuta")} />
                  </SelectTrigger>
                  <SelectContent>
                    {templates.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" variant="outline" disabled={busy || sending || !templateId} onClick={() => void fillFromTemplate()}>
                  {t("fillTemplate")}
                </Button>
              </div>
              <MinutaEditor key={`${row.id}-${editorKey}`} value={draft} tokens={tokens} onChange={setDraft} />
            </div>
          ) : null}
          {step === 2 ? (
            <div className="h-[min(68vh,720px)] overflow-hidden rounded-lg border bg-white">
              {previewLoading ? (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t("previewLoading")}
                </div>
              ) : previewError ? (
                <div className="flex h-full items-center justify-center px-4 text-center text-sm text-destructive">
                  {previewError}
                </div>
              ) : previewUrl ? (
                <iframe title={t("wizardPreview")} src={previewUrl} className="h-full w-full" />
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex items-center justify-between gap-2 border-t px-5 py-3">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => {
              if (step === 0) {
                onClose();
                return;
              }
              setStep(step - 1);
            }}
          >
            {step === 0 ? t("wizardClose") : t("wizardBack")}
          </Button>
          {step < 2 ? (
            <Button
              type="button"
              size="sm"
              disabled={step === 1 && !hasBody(draft)}
              onClick={() => {
                if (step === 0) {
                  void persistFacts().then((saved) => {
                    if (saved) {
                      void onChanged();
                      setStep(1);
                    }
                  });
                  return;
                }
                void openPreview();
              }}
            >
              {t("wizardNext")}
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              disabled={busy || sending || !hasBody(draft) || (!row.draft_html && !templateId)}
              onClick={() => void sendToSignature()}
            >
              {t("sendToSignature")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
