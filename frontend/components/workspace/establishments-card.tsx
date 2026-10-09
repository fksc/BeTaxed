"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { createEstablishment, patchEstablishment } from "@/lib/api/workspace-client";
import type { EstablishmentOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import type { AuthOpts } from "@/lib/api/http";

export function EstablishmentsCard({
  rows,
  canManage,
  opts,
  onChanged,
}: {
  rows: EstablishmentOut[];
  canManage: boolean;
  opts: AuthOpts;
  onChanged: () => Promise<void>;
}) {
  const t = useTranslations("workspace.settings");
  const [name, setName] = useState("");
  const [ssCode, setSsCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onAdd() {
    const trimmed = name.trim();
    if (!trimmed || !/^\d{4}$/.test(ssCode)) {
      setError(t("establishmentInvalid"));
      return;
    }
    setBusy(true);
    try {
      await createEstablishment({ name: trimmed, ss_code: ssCode }, opts);
      setName("");
      setSsCode("");
      setError(null);
      await onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(t("establishmentDuplicate"));
      } else if (err instanceof ApiError && err.status === 403) {
        setError(t("establishmentForbidden"));
      } else {
        setError(t("establishmentFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function onStatus(row: EstablishmentOut) {
    setBusy(true);
    try {
      await patchEstablishment(
        row.id,
        { status: row.status === "OPEN" ? "CLOSED" : "OPEN" },
        opts,
      );
      setError(null);
      await onChanged();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("establishmentForbidden"));
      } else {
        setError(t("establishmentFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("establishmentsTitle")}</CardTitle>
        <CardDescription className="text-xs">{t("establishmentsHint")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-1">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("establishmentEmpty")}</p>
        ) : (
          <ul className="space-y-2">
            {rows.map((row) => (
              <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span>
                  <span className="font-medium">{row.name}</span>
                  <span className="text-muted-foreground"> · {row.ss_code}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {row.status === "OPEN" ? t("establishmentOpen") : t("establishmentClosed")}
                  </span>
                </span>
                {canManage ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void onStatus(row)}
                  >
                    {row.status === "OPEN" ? t("establishmentClose") : t("establishmentReopen")}
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {canManage ? (
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t("establishmentName")} className="w-56">
              <Input
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="off"
              />
            </Field>
            <Field label={t("establishmentCode")} className="w-32">
              <Input
                value={ssCode}
                inputMode="numeric"
                maxLength={4}
                placeholder="0001"
                onChange={(event) => setSsCode(event.target.value.replace(/\D/g, "").slice(0, 4))}
                autoComplete="off"
              />
            </Field>
            <Button type="button" size="sm" disabled={busy} onClick={() => void onAdd()}>
              {t("establishmentAdd")}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
