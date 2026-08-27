"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { getMe, listPeople, patchPersonStatus, uploadPersonContract } from "@/lib/api/workspace-client";
import type { PersonOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

const STATUSES = ["ACTIVE", "ON_LEAVE", "TERMINATED"] as const;
const LEAVE_TYPES = ["PARENTAL", "SICKNESS", "UNPAID", "OTHER"] as const;
const MODALITIES = ["SEM_TERMO", "TERMO_CERTO", "TERMO_INCERTO", "OTHER"] as const;

function reviewLabel(status: string | null, t: (key: string) => string): string {
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

function sourceLabel(source: string, t: (key: string) => string): string {
  if (source === "USER" || source === "ADMIN") {
    return t("people.sourceUser");
  }
  if (source === "HRMS") {
    return t("people.sourceHrms");
  }
  return t("people.sourceSs");
}

function modalityLabel(value: string | null, t: (key: string) => string): string {
  if (!value) {
    return t("people.modalityUnknown");
  }
  if (
    value === "SEM_TERMO" ||
    value === "TERMO_CERTO" ||
    value === "TERMO_INCERTO" ||
    value === "OTHER"
  ) {
    return t(`people.modality.${value}`);
  }
  return value;
}

export function PeoplePage() {
  const t = useTranslations("workspace");
  const [rows, setRows] = useState<PersonOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [canOverride, setCanOverride] = useState(false);
  const [leaveById, setLeaveById] = useState<Record<string, (typeof LEAVE_TYPES)[number]>>(
    {},
  );
  const [filterModality, setFilterModality] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterFile, setFilterFile] = useState("all");
  const inputRef = useRef<HTMLInputElement>(null);
  const [targetId, setTargetId] = useState<string | null>(null);

  async function reload() {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      setError(t("needSession"));
      return;
    }
    const [people, me] = await Promise.all([
      listPeople({ idToken, companyId }),
      getMe({ idToken }),
    ]);
    const membership = me.memberships.find((row) => row.company_id === companyId);
    setCanOverride(
      me.user_type === "BETAXED_STAFF" ||
        membership?.role === "ADMIN" ||
        membership?.role === "HR",
    );
    setRows(people);
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needSession")));
  }, [t]);

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      if (filterModality === "missing" && row.contract_modality) {
        return false;
      }
      if (
        filterModality !== "all" &&
        filterModality !== "missing" &&
        row.contract_modality !== filterModality
      ) {
        return false;
      }
      if (filterStatus !== "all" && row.status !== filterStatus) {
        return false;
      }
      if (filterFile === "missing" && row.has_contract) {
        return false;
      }
      if (filterFile === "onFile" && !row.has_contract) {
        return false;
      }
      return true;
    });
  }, [rows, filterModality, filterStatus, filterFile]);

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

  async function onStatus(
    employeeId: string,
    status: (typeof STATUSES)[number],
    leaveType?: (typeof LEAVE_TYPES)[number],
  ) {
    const idToken = await currentIdToken();
    const companyId = loadCompanyId();
    if (!idToken || !companyId) {
      return;
    }
    setBusyId(employeeId);
    try {
      await patchPersonStatus(
        employeeId,
        status === "ON_LEAVE"
          ? { status, leave_type: leaveType ?? leaveById[employeeId] ?? "OTHER" }
          : { status },
        { idToken, companyId },
      );
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(t("people.statusForbidden"));
      } else {
        setError(t("people.statusFailed"));
      }
    } finally {
      setBusyId(null);
    }
  }

  return (
    <ShellPage crumb={t("peopleCrumb")}>
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
          <CardContent className="space-y-4 pt-1">
            <div className="flex flex-wrap items-end gap-3">
              <Field label={t("people.filterModality")} className="w-48">
                <Select
                  value={filterModality}
                  onValueChange={(value) => value && setFilterModality(value)}
                  items={{
                    all: t("people.filterAll"),
                    SEM_TERMO: t("people.modality.SEM_TERMO"),
                    TERMO_CERTO: t("people.modality.TERMO_CERTO"),
                    TERMO_INCERTO: t("people.modality.TERMO_INCERTO"),
                    OTHER: t("people.modality.OTHER"),
                    missing: t("people.modalityUnknown"),
                  }}
                >
                  <SelectTrigger aria-label={t("people.filterModality")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("people.filterAll")}</SelectItem>
                    {MODALITIES.map((item) => (
                      <SelectItem key={item} value={item}>
                        {t(`people.modality.${item}`)}
                      </SelectItem>
                    ))}
                    <SelectItem value="missing">{t("people.modalityUnknown")}</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("people.filterStatus")} className="w-40">
                <Select
                  value={filterStatus}
                  onValueChange={(value) => value && setFilterStatus(value)}
                  items={{
                    all: t("people.filterAll"),
                    ACTIVE: t("people.status.ACTIVE"),
                    ON_LEAVE: t("people.status.ON_LEAVE"),
                    TERMINATED: t("people.status.TERMINATED"),
                  }}
                >
                  <SelectTrigger aria-label={t("people.filterStatus")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("people.filterAll")}</SelectItem>
                    {STATUSES.map((status) => (
                      <SelectItem key={status} value={status}>
                        {t(`people.status.${status}`)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label={t("people.filterFile")} className="w-44">
                <Select
                  value={filterFile}
                  onValueChange={(value) => value && setFilterFile(value)}
                  items={{
                    all: t("people.filterAll"),
                    missing: t("people.filterMissingFile"),
                    onFile: t("people.filterOnFile"),
                  }}
                >
                  <SelectTrigger aria-label={t("people.filterFile")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("people.filterAll")}</SelectItem>
                    <SelectItem value="missing">{t("people.filterMissingFile")}</SelectItem>
                    <SelectItem value="onFile">{t("people.filterOnFile")}</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            </div>
            {rows.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("people.empty")}</p>
            ) : filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("people.filterEmpty")}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-muted-foreground">
                    <tr className="border-b">
                      <th className="py-2 pr-3 font-medium">{t("people.colName")}</th>
                      <th className="py-2 pr-3 font-medium">{t("people.colModality")}</th>
                      <th className="py-2 pr-3 font-medium">{t("people.statusLabel")}</th>
                      <th className="py-2 pr-3 font-medium">{t("people.colFile")}</th>
                      <th className="py-2 font-medium">{t("people.colActions")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row) => (
                      <tr key={row.id} className="border-b border-border/60 last:border-0">
                        <td className="py-2 pr-3 align-top">
                          <div className="font-medium">{row.display_name || t("people.unnamed")}</div>
                          <div className="text-xs text-muted-foreground">
                            {sourceLabel(row.status_source, t)}
                          </div>
                          {row.has_source_conflict ? (
                            <div className="text-xs text-destructive">{t("people.conflict")}</div>
                          ) : null}
                        </td>
                        <td className="py-2 pr-3 align-top">
                          {modalityLabel(row.contract_modality, t)}
                        </td>
                        <td className="py-2 pr-3 align-top">
                          {canOverride ? (
                            <div className="flex flex-col gap-2">
                              <Select
                                value={row.status}
                                disabled={busyId === row.id}
                                onValueChange={(value) => {
                                  if (!value) {
                                    return;
                                  }
                                  void onStatus(row.id, value as (typeof STATUSES)[number]);
                                }}
                                items={Object.fromEntries(
                                  STATUSES.map((status) => [status, t(`people.status.${status}`)]),
                                )}
                              >
                                <SelectTrigger
                                  className="w-36"
                                  aria-label={t("people.statusLabel")}
                                >
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {STATUSES.map((status) => (
                                    <SelectItem key={status} value={status}>
                                      {t(`people.status.${status}`)}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              {row.status === "ON_LEAVE" ? (
                                <Select
                                  value={leaveById[row.id] ?? row.leave_type ?? "OTHER"}
                                  disabled={busyId === row.id}
                                  onValueChange={(value) => {
                                    if (!value) {
                                      return;
                                    }
                                    const leave = value as (typeof LEAVE_TYPES)[number];
                                    setLeaveById((current) => ({
                                      ...current,
                                      [row.id]: leave,
                                    }));
                                    void onStatus(row.id, "ON_LEAVE", leave);
                                  }}
                                  items={Object.fromEntries(
                                    LEAVE_TYPES.map((leave) => [leave, t(`people.leave.${leave}`)]),
                                  )}
                                >
                                  <SelectTrigger
                                    className="w-36"
                                    aria-label={t("people.leaveLabel")}
                                  >
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    {LEAVE_TYPES.map((leave) => (
                                      <SelectItem key={leave} value={leave}>
                                        {t(`people.leave.${leave}`)}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-muted-foreground">
                              {t(`people.status.${row.status}`)}
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-3 align-top">
                          {row.has_contract ? (
                            reviewLabel(row.review_status, t)
                          ) : (
                            <span className="text-destructive">{t("people.noFile")}</span>
                          )}
                        </td>
                        <td className="py-2 align-top">
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
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
    </ShellPage>
  );
}
