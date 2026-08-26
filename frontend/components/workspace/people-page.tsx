"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellAppBar } from "@/components/shell/shell-app-bar";
import { getMe, listPeople, patchPersonStatus, uploadPersonContract } from "@/lib/api/workspace-client";
import type { PersonOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { loadCompanyId } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";

const STATUSES = ["ACTIVE", "ON_LEAVE", "TERMINATED"] as const;
const LEAVE_TYPES = ["PARENTAL", "SICKNESS", "UNPAID", "OTHER"] as const;

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50";

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

export function PeoplePage() {
  const t = useTranslations("workspace");
  const [rows, setRows] = useState<PersonOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [canOverride, setCanOverride] = useState(false);
  const [leaveById, setLeaveById] = useState<Record<string, (typeof LEAVE_TYPES)[number]>>(
    {},
  );
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
                  className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 py-2 last:border-0"
                >
                  <div className="min-w-40">
                    <div className="text-sm font-medium">
                      {row.display_name || t("people.unnamed")}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {reviewLabel(row.review_status, t)} · {sourceLabel(row.status_source, t)}
                    </div>
                    {row.has_source_conflict ? (
                      <div className="text-xs text-destructive">{t("people.conflict")}</div>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {canOverride ? (
                      <>
                        <select
                          className={selectClass}
                          aria-label={t("people.statusLabel")}
                          value={row.status}
                          disabled={busyId === row.id}
                          onChange={(event) => {
                            const next = event.target.value as (typeof STATUSES)[number];
                            void onStatus(row.id, next);
                          }}
                        >
                          {STATUSES.map((status) => (
                            <option key={status} value={status}>
                              {t(`people.status.${status}`)}
                            </option>
                          ))}
                        </select>
                        {row.status === "ON_LEAVE" ? (
                          <select
                            className={selectClass}
                            aria-label={t("people.leaveLabel")}
                            value={leaveById[row.id] ?? row.leave_type ?? "OTHER"}
                            disabled={busyId === row.id}
                            onChange={(event) => {
                              const leave = event.target
                                .value as (typeof LEAVE_TYPES)[number];
                              setLeaveById((current) => ({
                                ...current,
                                [row.id]: leave,
                              }));
                              void onStatus(row.id, "ON_LEAVE", leave);
                            }}
                          >
                            {LEAVE_TYPES.map((leave) => (
                              <option key={leave} value={leave}>
                                {t(`people.leave.${leave}`)}
                              </option>
                            ))}
                          </select>
                        ) : null}
                      </>
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {t(`people.status.${row.status}`)}
                      </span>
                    )}
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
