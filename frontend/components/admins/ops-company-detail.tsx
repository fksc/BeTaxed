"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { FileText, Users, UserCheck, CalendarDays } from "lucide-react";

import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { MembersPanel } from "@/components/workspace/members-panel";
import { StatCard } from "@/components/workspace/stat-card";
import {
  getOpsCompany,
  listHeadcountMonths,
  listPeople,
  listSsBatches,
  patchOpsCompany,
  uploadPersonContract,
} from "@/lib/api/workspace-client";
import type {
  HeadcountMonthOut,
  OpsCompanyDetailOut,
  PersonOut,
  SsBatchOut,
} from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";
import { cn } from "@/lib/utils";

const HUB_TABS = ["overview", "vinculos", "employees", "documents"] as const;
type HubTab = (typeof HUB_TABS)[number];

function isHubTab(value: string | null): value is HubTab {
  return HUB_TABS.includes(value as HubTab);
}

function ym(value: string): string {
  return value.slice(0, 7);
}

function currentYearMonth(): { year: string; month: string } {
  const now = new Date();
  return {
    year: String(now.getFullYear()),
    month: String(now.getMonth() + 1).padStart(2, "0"),
  };
}

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

export function OpsCompanyDetailPage({ companyId }: { companyId: string }) {
  const t = useTranslations("admins.companyDetail");
  const tm = useTranslations("members");
  const tw = useTranslations("workspace");
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tabParam = searchParams.get("tab");
  const tab: HubTab = isHubTab(tabParam) ? tabParam : "overview";

  const [row, setRow] = useState<OpsCompanyDetailOut | null>(null);
  const [people, setPeople] = useState<PersonOut[]>([]);
  const [batches, setBatches] = useState<SsBatchOut[]>([]);
  const [headcounts, setHeadcounts] = useState<HeadcountMonthOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [maxMembers, setMaxMembers] = useState("3");
  const [busy, setBusy] = useState(false);
  const [idToken, setIdToken] = useState<string | null>(null);
  const nowYm = currentYearMonth();
  const [year, setYear] = useState(nowYm.year);
  const [month, setMonth] = useState(nowYm.month);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploadTarget, setUploadTarget] = useState<string | null>(null);

  async function reload() {
    const token = await currentIdToken();
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setIdToken(token);
    const opts = { idToken: token, companyId };
    const [detail, nextPeople, nextBatches, nextHeadcounts] = await Promise.all([
      getOpsCompany(companyId, { idToken: token }),
      listPeople(opts),
      listSsBatches(opts),
      listHeadcountMonths(opts),
    ]);
    setRow(detail);
    setPeople(nextPeople);
    setBatches(nextBatches);
    setHeadcounts(nextHeadcounts);
    setMaxMembers(String(detail.max_members));
    setError(null);
  }

  useEffect(() => {
    void reload().catch(() => setError(t("needAuth")));
  }, [companyId, t]);

  const years = useMemo(() => {
    const set = new Set<string>([nowYm.year]);
    for (const batch of batches) {
      set.add(ym(batch.period_year_month).slice(0, 4));
    }
    for (const hc of headcounts) {
      set.add(ym(hc.year_month).slice(0, 4));
    }
    return [...set].sort((a, b) => Number(b) - Number(a));
  }, [batches, headcounts, nowYm.year]);

  const selectedYm = `${year}-${month}`;
  const batchForMonth = batches.find((batch) => ym(batch.period_year_month) === selectedYm) ?? null;
  const headcountForMonth = headcounts.find(
    (item) => item.source === "SS_BATCH" && ym(item.year_month) === selectedYm,
  );
  const contractsOnFile = people.filter((person) => person.has_contract).length;
  const latestBatch = batches[0] ?? null;

  function goTab(next: HubTab) {
    const href = next === "overview" ? pathname : `${pathname}?tab=${next}`;
    router.replace(href);
  }

  async function onSaveCap() {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      return;
    }
    const parsed = Number(maxMembers);
    if (!Number.isInteger(parsed) || parsed < 1) {
      setError(t("capInvalid"));
      return;
    }
    setBusy(true);
    try {
      const detail = await patchOpsCompany(companyId, { max_members: parsed }, { idToken: token });
      setRow(detail);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("saveFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(employeeId: string, file: File | undefined) {
    if (!file || !idToken) {
      return;
    }
    setBusy(true);
    try {
      await uploadPersonContract(employeeId, file, { idToken, companyId });
      await reload();
    } catch {
      setError(t("uploadFailed"));
    } finally {
      setBusy(false);
    }
  }

  const tabs: { id: HubTab; label: string }[] = [
    { id: "overview", label: t("tabOverview") },
    { id: "vinculos", label: t("tabVinculos") },
    { id: "employees", label: t("tabEmployees") },
    { id: "documents", label: t("tabDocuments") },
  ];

  return (
    <ShellPage crumb={row?.legal_name ?? t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <Link
          href={paths.adminsCompanies}
          className="text-xs text-muted-foreground underline-offset-4 hover:underline"
        >
          {t("back")}
        </Link>
        <div className="text-base font-semibold">{row?.legal_name ?? t("title")}</div>
        <p className="text-sm text-muted-foreground">
          {row?.trading_name ? `${row.trading_name} · ` : ""}
          {row?.locale?.toUpperCase()}
        </p>
        <nav
          className="mt-3 flex w-fit rounded-lg border bg-muted/40 p-0.5 text-sm"
          aria-label={t("hubNavAria")}
        >
          {tabs.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => goTab(item.id)}
              className={cn(
                "rounded-md px-3 py-1 font-medium transition-colors",
                tab === item.id
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
              aria-current={tab === item.id ? "page" : undefined}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}

        {tab === "overview" && row ? (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard
                label={t("kpiEmployees")}
                value={String(people.length)}
                icon={<Users size={14} />}
              />
              <StatCard
                label={t("kpiContracts")}
                value={`${contractsOnFile}/${people.length || 0}`}
                icon={<FileText size={14} />}
              />
              <StatCard
                label={t("kpiHeadcount")}
                value={
                  latestBatch
                    ? String(
                        headcounts.find(
                          (item) =>
                            item.source === "SS_BATCH" &&
                            ym(item.year_month) === ym(latestBatch.period_year_month),
                        )?.headcount ?? "—",
                      )
                    : "—"
                }
                hint={latestBatch ? ym(latestBatch.period_year_month) : t("kpiNoSs")}
                icon={<UserCheck size={14} />}
              />
              <StatCard
                label={t("kpiSeats")}
                value={`${row.seats_used}/${row.max_members}`}
                icon={<CalendarDays size={14} />}
              />
            </div>
            <Card>
              <CardHeader>
                <CardTitle>{t("capTitle")}</CardTitle>
                <CardDescription>{t("capHint")}</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-end gap-3">
                <Field label={tm("maxMembers")} className="w-28">
                  <Input
                    type="number"
                    min={1}
                    value={maxMembers}
                    onChange={(event) => setMaxMembers(event.target.value)}
                  />
                </Field>
                <Button type="button" size="sm" disabled={busy} onClick={() => void onSaveCap()}>
                  {t("saveCap")}
                </Button>
              </CardContent>
            </Card>
            {idToken ? (
              <MembersPanel
                members={row.members}
                invites={row.invites}
                seatsUsed={row.seats_used}
                maxMembers={row.max_members}
                canInvite
                opts={{ idToken, companyId }}
                onChanged={reload}
              />
            ) : null}
          </>
        ) : null}

        {tab === "vinculos" ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("tabVinculos")}</CardTitle>
              <CardDescription>{t("vinculosLead")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex flex-wrap items-end gap-3">
                <Field label={t("year")} className="w-28">
                  <Select value={year} onValueChange={(value) => value && setYear(value)}>
                    <SelectTrigger aria-label={t("year")}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {years.map((item) => (
                        <SelectItem key={item} value={item}>
                          {item}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </Field>
                <Field label={t("month")} className="w-40">
                  <Select
                    value={month}
                    onValueChange={(value) => value && setMonth(value)}
                    items={{
                      "01": t("months.01"),
                      "02": t("months.02"),
                      "03": t("months.03"),
                      "04": t("months.04"),
                      "05": t("months.05"),
                      "06": t("months.06"),
                      "07": t("months.07"),
                      "08": t("months.08"),
                      "09": t("months.09"),
                      "10": t("months.10"),
                      "11": t("months.11"),
                      "12": t("months.12"),
                    }}
                  >
                    <SelectTrigger aria-label={t("month")}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 12 }, (_, index) => {
                        const value = String(index + 1).padStart(2, "0");
                        return (
                          <SelectItem key={value} value={value}>
                            {t(`months.${value}`)}
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              {batchForMonth ? (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <StatCard
                    label={tw("declarations.joiners")}
                    value={String(batchForMonth.event_counts.HIRED ?? 0)}
                  />
                  <StatCard
                    label={tw("declarations.leavers")}
                    value={String(batchForMonth.event_counts.TERMINATED ?? 0)}
                  />
                  <StatCard
                    label={t("kpiHeadcount")}
                    value={headcountForMonth ? String(headcountForMonth.headcount) : "—"}
                  />
                  <StatCard
                    label={tw("declarations.statusApplied")}
                    value={batchForMonth.parse_status}
                  />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{t("vinculosEmpty")}</p>
              )}
              {people.length > 0 ? (
                <EmployeeTable people={people} tw={tw} contractLabel={t("contractCol")} />
              ) : null}
            </CardContent>
          </Card>
        ) : null}

        {tab === "employees" ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("tabEmployees")}</CardTitle>
              <CardDescription>{tw("people.hint")}</CardDescription>
            </CardHeader>
            <CardContent>
              {people.length === 0 ? (
                <p className="text-sm text-muted-foreground">{tw("people.empty")}</p>
              ) : (
                <EmployeeTable people={people} tw={tw} contractLabel={t("contractCol")} />
              )}
            </CardContent>
          </Card>
        ) : null}

        {tab === "documents" ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("tabDocuments")}</CardTitle>
              <CardDescription>{t("documentsLead")}</CardDescription>
            </CardHeader>
            <CardContent>
              {people.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("documentsEmpty")}</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs text-muted-foreground">
                      <tr className="border-b">
                        <th className="py-2 pr-3 font-medium">{tw("people.title")}</th>
                        <th className="py-2 pr-3 font-medium">{t("contractCol")}</th>
                        <th className="py-2 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {people.map((person) => (
                        <tr key={person.id} className="border-b border-border/60 last:border-0">
                          <td className="py-2 pr-3 font-medium">
                            {person.display_name || tw("people.unnamed")}
                          </td>
                          <td className="py-2 pr-3 text-muted-foreground">
                            {reviewLabel(person.review_status, tw)}
                          </td>
                          <td className="py-2 text-right">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={busy}
                              onClick={() => {
                                setUploadTarget(person.id);
                                fileRef.current?.click();
                              }}
                            >
                              {tw("people.upload")}
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
        ) : null}
      </div>
      <input
        ref={fileRef}
        type="file"
        className="sr-only"
        accept="application/pdf,.pdf"
        onChange={(event) => {
          const file = event.target.files?.[0];
          event.target.value = "";
          if (uploadTarget) {
            void onUpload(uploadTarget, file);
          }
        }}
      />
    </ShellPage>
  );
}

function EmployeeTable({
  people,
  tw,
  contractLabel,
}: {
  people: PersonOut[];
  tw: ReturnType<typeof useTranslations>;
  contractLabel: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-3 font-medium">{tw("people.title")}</th>
            <th className="py-2 pr-3 font-medium">{tw("people.statusLabel")}</th>
            <th className="py-2 font-medium">{contractLabel}</th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.id} className="border-b border-border/60 last:border-0">
              <td className="py-2 pr-3 font-medium">
                {person.display_name || tw("people.unnamed")}
              </td>
              <td className="py-2 pr-3">
                {person.status === "ACTIVE"
                  ? tw("people.status.ACTIVE")
                  : person.status === "ON_LEAVE"
                    ? tw("people.status.ON_LEAVE")
                    : tw("people.status.TERMINATED")}
              </td>
              <td className="py-2 text-muted-foreground">
                {reviewLabel(person.review_status, tw)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
