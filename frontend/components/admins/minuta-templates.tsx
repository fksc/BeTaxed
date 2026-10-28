"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

import { MinutaEditor } from "@/components/admins/minuta-editor";
import { MinutaPreviewDialog } from "@/components/admins/minuta-preview-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ShellPage } from "@/components/shell/shell-app-bar";
import {
  createMinutaTemplate,
  listMinutaTemplates,
  listMinutaTokens,
  patchMinutaTemplate,
  previewMinutaPdf,
} from "@/lib/api/workspace-client";
import type { MinutaTemplateOut, MinutaTokenOut } from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";

export function MinutaTemplatesPage() {
  const t = useTranslations("admins.templates");
  const [rows, setRows] = useState<MinutaTemplateOut[]>([]);
  const [tokens, setTokens] = useState<MinutaTokenOut[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("<p></p>");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("needAuth"));
      return;
    }
    const opts = { idToken };
    const [templates, catalogue] = await Promise.all([
      listMinutaTemplates(opts, true),
      listMinutaTokens(opts),
    ]);
    setRows(templates);
    setTokens(catalogue);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needAuth")));
  }, [t]);

  function openRow(row: MinutaTemplateOut) {
    setSelected(row.id);
    setCode(row.code);
    setTitle(row.title);
    setBody(row.body_html);
    setNotice(null);
  }

  function startNew() {
    setSelected(null);
    setCode("");
    setTitle("");
    setBody("<p></p>");
    setNotice(null);
  }

  async function onSave() {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusy(true);
    try {
      if (selected) {
        const saved = await patchMinutaTemplate(
          selected,
          { title, body_html: body },
          { idToken },
        );
        openRow(saved);
      } else {
        const saved = await createMinutaTemplate(
          { code, title, body_html: body },
          { idToken },
        );
        openRow(saved);
      }
      await reload();
      setNotice(t("saved"));
    } catch {
      setError(t("needAuth"));
    } finally {
      setBusy(false);
    }
  }

  async function onPreview() {
    const idToken = await currentIdToken();
    if (!idToken) {
      setPreviewError(t("needAuth"));
      setPreviewOpen(true);
      return;
    }
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
    try {
      const blob = await previewMinutaPdf(body, { idToken });
      setPreviewUrl(URL.createObjectURL(blob));
    } catch {
      setPreviewError(t("previewFailed"));
    } finally {
      setPreviewLoading(false);
    }
  }

  function closePreview() {
    setPreviewOpen(false);
    setPreviewUrl((current) => {
      if (current) {
        URL.revokeObjectURL(current);
      }
      return null;
    });
  }

  async function onToggle(row: MinutaTemplateOut) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    await patchMinutaTemplate(row.id, { is_active: !row.is_active }, { idToken });
    await reload();
  }

  return (
    <ShellPage crumb={t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <div className="grid gap-4 p-4 sm:p-6 lg:grid-cols-[16rem_1fr]">
        <div className="space-y-2">
          <Button type="button" size="sm" variant="outline" onClick={startNew}>
            {t("create")}
          </Button>
          {rows.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("empty")}</p>
          ) : (
            rows.map((row) => (
              <button
                key={row.id}
                type="button"
                className="block w-full rounded-md border border-border px-3 py-2 text-left text-sm hover:bg-muted"
                onClick={() => openRow(row)}
              >
                <span className="font-medium">{row.title}</span>
                {row.is_active ? null : (
                  <span className="ml-2 text-xs text-muted-foreground">{t("inactive")}</span>
                )}
              </button>
            ))
          )}
        </div>
        <div className="space-y-3">
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          {notice ? <p className="text-sm text-muted-foreground">{notice}</p> : null}
          <label className="block space-y-1 text-sm">
            <span>{t("code")}</span>
            <Input value={code} disabled={selected != null} onChange={(event) => setCode(event.target.value)} />
          </label>
          <label className="block space-y-1 text-sm">
            <span>{t("name")}</span>
            <Input value={title} onChange={(event) => setTitle(event.target.value)} />
          </label>
          <div className="space-y-1 text-sm">
            <div>{t("body")}</div>
            <MinutaEditor key={selected ?? "new"} value={body} tokens={tokens} onChange={setBody} />
          </div>
          <div className="flex gap-2">
            <Button type="button" size="sm" variant="outline" onClick={() => void onPreview()}>
              {t("preview")}
            </Button>
            <Button type="button" size="sm" disabled={busy || !title || !code} onClick={() => void onSave()}>
              {selected ? t("save") : t("create")}
            </Button>
            {selected ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  const row = rows.find((item) => item.id === selected);
                  if (row) {
                    void onToggle(row);
                  }
                }}
              >
                {rows.find((item) => item.id === selected)?.is_active ? t("deactivate") : t("activate")}
              </Button>
            ) : null}
          </div>
        </div>
      </div>
      <MinutaPreviewDialog
        open={previewOpen}
        title={t("previewTitle")}
        loading={previewLoading}
        error={previewError}
        pdfUrl={previewUrl}
        loadingLabel={t("previewLoading")}
        saveLabel={selected ? t("save") : t("create")}
        backLabel={t("backToEdit")}
        saveDisabled={busy || !title || !code}
        onSave={() => void onSave()}
        onBack={closePreview}
      />
    </ShellPage>
  );
}
