"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  ArrowLeftRight,
  CalendarCheck,
  CalendarOff,
  Percent,
  UserMinus,
  UserPlus,
  Users,
  Wallet,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { MonthPicker } from "@/components/ui/month-picker";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { Dropzone } from "@/components/intake/dropzone";
import { Field } from "@/components/intake/field";
import { StatCard } from "@/components/workspace/stat-card";
import {
  listHeadcountMonths,
  listSsBatches,
  putUserHeadcount,
  uploadCompanySs,
} from "@/lib/api/workspace-client";
import type { HeadcountMonthOut, SsBatchOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

function currentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function ym(value: string): string {
  return value.slice(0, 7);
}

function eventCount(batch: SsBatchOut | null, key: string): number {
  if (!batch) {
    return 0;
  }
  return batch.event_counts[key] ?? 0;
}

function statusLabel(status: string, t: (key: string) => string): string {
  if (status === "APPLIED") {
    return t("declarations.statusApplied");
  }
  if (status === "FAILED") {
    return t("declarations.statusFailed");
  }
  if (status === "PARSED") {
    return t("declarations.statusParsed");
  }
  if (status === "PENDING") {
    return t("declarations.statusPending");
  }
  return status;
}

export function DeclarationsPage() {
  const t = useTranslations("workspace");
  const [batches, setBatches] = useState<SsBatchOut[]>([]);
  const [headcounts, setHeadcounts] = useState<HeadcountMonthOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [period, setPeriod] = useState(currentMonth);
  const [userMonth, setUserMonth] = useState(currentMonth);
  const [userCount, setUserCount] = useState("0");
  const [vinculos, setVinculos] = useState<File[]>([]);
  const [contratos, setContratos] = useState<File[]>([]);

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("needSession"));
      return;
    }
    const [nextBatches, nextHeadcounts] = await Promise.all([
      listSsBatches({ idToken, companyId }),
      listHeadcountMonths({ idToken, companyId }),
    ]);
    setBatches(nextBatches);
    setHeadcounts(nextHeadcounts);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needSession")));
  }, [t]);

  const latest = batches[0] ?? null;
  const ssForPeriod = headcounts.find(
    (row) => row.source === "SS_BATCH" && ym(row.year_month) === (latest ? ym(latest.period_year_month) : period),
  );
  const userForForm = headcounts.find(
    (row) => row.source === "USER" && ym(row.year_month) === userMonth,
  );

  async function onUpload() {
    const files = [...vinculos, ...contratos];
    const unique = files.filter(
      (file, index) => files.findIndex((other) => other.name === file.name && other.size === file.size) === index,
    );
    if (unique.length === 0) {
      setError(t("declarations.needBoth"));
      return;
    }
    const hasBoth = vinculos.length > 0 && contratos.length > 0;
    const combinedOnly =
      unique.length === 1 && unique[0].name.toLowerCase().endsWith(".xlsx");
    if (!hasBoth && !combinedOnly) {
      setError(t("declarations.needBoth"));
      return;
    }
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusy(true);
    try {
      await uploadCompanySs(unique, period, { idToken, companyId });
      setVinculos([]);
      setContratos([]);
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("declarations.forbidden"));
      } else if (err instanceof ApiError && err.status === 409) {
        setError(t("declarations.nissMismatch"));
      } else {
        setError(t("declarations.uploadFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

  async function onUserHeadcount() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    const parsed = Number.parseInt(userCount, 10);
    if (Number.isNaN(parsed) || parsed < 0) {
      setError(t("declarations.headcountInvalid"));
      return;
    }
    setBusy(true);
    try {
      await putUserHeadcount(userMonth, parsed, { idToken, companyId });
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("declarations.forbidden"));
      } else {
        setError(t("declarations.headcountFailed"));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <ShellPage crumb={t("declarationsCrumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <div className="text-base font-semibold">{t("nav.declarations")}</div>
        <p className="text-sm text-muted-foreground">{t("declarations.lead")}</p>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("declarations.uploadTitle")}</CardTitle>
            <CardDescription className="text-xs">{t("declarations.hint")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-1">
            <Field label={t("declarations.month")} className="w-56">
              <MonthPicker id="ss-period" value={period} onChange={setPeriod} />
            </Field>
            <p className="text-sm text-muted-foreground">{t("declarations.needBoth")}</p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Dropzone
                files={vinculos}
                disabled={busy}
                multiple={false}
                title={t("declarations.vinculosTitle")}
                hint={t("declarations.vinculosHint")}
                onFiles={setVinculos}
              />
              <Dropzone
                files={contratos}
                disabled={busy}
                multiple={false}
                title={t("declarations.contratosTitle")}
                hint={t("declarations.contratosHint")}
                onFiles={setContratos}
              />
            </div>
            <Button type="button" size="sm" disabled={busy} onClick={() => void onUpload()}>
              {t("declarations.upload")}
            </Button>
          </CardContent>
        </Card>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label={t("declarations.joiners")}
            value={String(eventCount(latest, "HIRED"))}
            icon={<UserPlus size={14} />}
          />
          <StatCard
            label={t("declarations.leavers")}
            value={String(eventCount(latest, "TERMINATED"))}
            icon={<UserMinus size={14} />}
          />
          <StatCard
            label={t("declarations.rehires")}
            value={String(eventCount(latest, "REHIRED"))}
            icon={<Users size={14} />}
          />
          <StatCard
            label={t("declarations.pay")}
            value={String(eventCount(latest, "SALARY_CHANGED"))}
            icon={<Wallet size={14} />}
          />
          <StatCard
            label={t("declarations.modality")}
            value={String(eventCount(latest, "MODALITY_CHANGED"))}
            icon={<ArrowLeftRight size={14} />}
          />
          <StatCard
            label={t("declarations.taxa")}
            value={String(eventCount(latest, "TSU_RATE_CHANGED"))}
            icon={<Percent size={14} />}
          />
          <StatCard
            label={t("declarations.missing")}
            value={String(eventCount(latest, "MISSING_FROM_DECLARATION"))}
            icon={<AlertTriangle size={14} />}
          />
          <StatCard
            label={t("declarations.conflicts")}
            value={String(eventCount(latest, "SOURCE_CONFLICT"))}
            icon={<AlertTriangle size={14} />}
          />
          <StatCard
            label={t("declarations.leaveStarted")}
            value={String(eventCount(latest, "LEAVE_STARTED"))}
            icon={<CalendarOff size={14} />}
          />
          <StatCard
            label={t("declarations.leaveEnded")}
            value={String(eventCount(latest, "LEAVE_ENDED"))}
            icon={<CalendarCheck size={14} />}
          />
        </div>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("declarations.batchesTitle")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-1">
            {batches.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("declarations.empty")}</p>
            ) : (
              batches.map((batch) => (
                <div
                  key={batch.id}
                  className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 py-2 last:border-0"
                >
                  <div>
                    <div className="text-sm font-medium">{ym(batch.period_year_month)}</div>
                    <div className="text-xs text-muted-foreground">
                      {statusLabel(batch.parse_status, t)}
                      {batch.parse_error ? ` · ${batch.parse_error}` : ""}
                    </div>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{t("declarations.headcountTitle")}</CardTitle>
            <CardDescription className="text-xs">{t("declarations.headcountLead")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-1">
            <p className="text-sm text-muted-foreground">
              {t("declarations.ssHeadcount", {
                month: latest ? ym(latest.period_year_month) : "—",
                count: ssForPeriod ? String(ssForPeriod.headcount) : "—",
              })}
            </p>
            <div className="flex flex-wrap items-end gap-3">
              <Field label={t("declarations.month")} className="w-56">
                <MonthPicker id="user-month" value={userMonth} onChange={setUserMonth} />
              </Field>
              <Field label={t("declarations.userHeadcount")} className="w-32">
                <Input
                  id="user-count"
                  type="number"
                  min={0}
                  value={userCount}
                  onChange={(event) => setUserCount(event.target.value)}
                />
              </Field>
              <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => void onUserHeadcount()}>
                {t("declarations.saveUser")}
              </Button>
            </div>
            {userForForm ? (
              <p className="text-xs text-muted-foreground">
                {t("declarations.userSaved", { count: String(userForForm.headcount) })}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </ShellPage>
  );
}
