"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { Columns3, Eye, FileText, Upload, UserCheck, UserPlus, Users, CalendarDays } from "lucide-react";

import { Field } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShellPage } from "@/components/shell/shell-app-bar";
import {
  ContractBatchModal,
  contractUploadRows,
  runContractUploads,
  type ContractUploadRow,
} from "@/components/workspace/contract-batch-modal";
import { RequestPipeline } from "@/components/admins/request-pipeline";
import { MembersPanel } from "@/components/workspace/members-panel";
import { StatCard } from "@/components/workspace/stat-card";
import {
  getOpsCompany,
  listEstablishments,
  listHeadcountMonths,
  listPeople,
  listSsBatches,
  openPersonContract,
  openRequestCase,
  patchOpsCompany,
  patchPersonStatus,
} from "@/lib/api/workspace-client";
import type {
  EstablishmentOut,
  HeadcountMonthOut,
  OpsCompanyDetailOut,
  BenefitBlockOut,
  PersonOut,
  SsBatchOut,
  TermBenefitOut,
} from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";
import { cn } from "@/lib/utils";

const HUB_TABS = ["overview", "vinculos", "employees", "pipeline", "already", "documents"] as const;
type HubTab = (typeof HUB_TABS)[number];
const STATUSES = ["ACTIVE", "ON_LEAVE", "TERMINATED"] as const;
const LEAVE_TYPES = ["PARENTAL", "SICKNESS", "UNPAID", "OTHER"] as const;
const MODALITIES = ["SEM_TERMO", "TERMO_CERTO", "TERMO_INCERTO", "OTHER"] as const;
type SortKey = "name" | "age" | "start" | "modality" | "status" | "file";

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

function foldName(value: string): string {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase();
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
  const [establishments, setEstablishments] = useState<EstablishmentOut[]>([]);
  const [establishmentId, setEstablishmentId] = useState("all");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [leaveById, setLeaveById] = useState<Record<string, (typeof LEAVE_TYPES)[number]>>(
    {},
  );
  const fileRef = useRef<HTMLInputElement>(null);
  const batchRef = useRef<HTMLInputElement>(null);
  const [batchNote, setBatchNote] = useState<string | null>(null);
  const [uploadRows, setUploadRows] = useState<ContractUploadRow[] | null>(null);
  const [uploadRunning, setUploadRunning] = useState(false);
  const [uploadTarget, setUploadTarget] = useState<string | null>(null);

  async function addToPipeline(employeeId: string) {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setBusyId(employeeId);
    try {
      await openRequestCase(employeeId, { idToken: token });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("needAuth"));
    } finally {
      setBusyId(null);
    }
  }

  async function reload(nextEstablishmentId = establishmentId) {
    const token = await currentIdToken();
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setIdToken(token);
    const opts = { idToken: token, companyId };
    const site = nextEstablishmentId === "all" ? null : nextEstablishmentId;
    const [detail, nextPeople, nextBatches, nextHeadcounts, sites] = await Promise.all([
      getOpsCompany(companyId, { idToken: token }),
      listPeople(opts, site),
      listSsBatches(opts),
      listHeadcountMonths(opts),
      listEstablishments(opts),
    ]);
    setRow(detail);
    setPeople(nextPeople);
    setBatches(nextBatches);
    setHeadcounts(nextHeadcounts);
    setEstablishments(sites);
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
  const alreadyBenefiting = people.filter((person) => person.already_on_ss_reduction);
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

  async function onShow(employeeId: string, documentId: string) {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    try {
      await openPersonContract(employeeId, documentId, { idToken: token, companyId });
    } catch {
      setError(t("uploadFailed"));
    }
  }

  async function startUploads(files: File[], employeeId?: string) {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setError(null);
    setBatchNote(null);
    setUploadRows(contractUploadRows(files));
    setUploadRunning(true);
    try {
      await runContractUploads({
        files,
        companyId,
        employeeId,
        getIdToken: (forceRefresh) => currentIdToken(forceRefresh),
        onRows: setUploadRows,
      });
    } finally {
      setUploadRunning(false);
    }
  }

  async function onUpload(employeeId: string, file: File | undefined) {
    if (!file) {
      return;
    }
    await startUploads([file], employeeId);
  }

  async function onBatch(files: File[]) {
    await startUploads(files);
  }

  async function onPersonStatus(
    employeeId: string,
    status: (typeof STATUSES)[number],
    leaveType?: (typeof LEAVE_TYPES)[number],
  ) {
    const token = idToken ?? (await currentIdToken());
    if (!token) {
      setError(t("needAuth"));
      return;
    }
    setBusyId(employeeId);
    try {
      await patchPersonStatus(
        employeeId,
        status === "ON_LEAVE"
          ? { status, leave_type: leaveType ?? leaveById[employeeId] ?? "OTHER" }
          : { status },
        { idToken: token, companyId },
      );
      await reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setError(tw("people.statusForbidden"));
      } else {
        setError(tw("people.statusFailed"));
      }
    } finally {
      setBusyId(null);
    }
  }

  const tabs: { id: HubTab; label: string }[] = [
    { id: "overview", label: t("tabOverview") },
    { id: "vinculos", label: t("tabVinculos") },
    { id: "employees", label: t("tabEmployees") },
    { id: "pipeline", label: t("tabPipeline") },
    { id: "already", label: t("tabAlready") },
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

        {tab === "pipeline" ? <RequestPipeline fixedCompanyId={companyId} /> : null}

        {tab === "employees" ? (
          <StaffPeopleCard
            companyId={companyId}
            people={people}
            establishments={establishments}
            establishmentId={establishmentId}
            onEstablishment={(value) => {
              setEstablishmentId(value);
              void reload(value).catch(() => setError(t("needAuth")));
            }}
            busyId={busyId}
            uploadsLocked={uploadRows !== null}
            leaveById={leaveById}
            onLeave={(employeeId, leave) =>
              setLeaveById((current) => ({ ...current, [employeeId]: leave }))
            }
            onShow={(employeeId, documentId) => void onShow(employeeId, documentId)}
            onUploadClick={(employeeId) => {
              setUploadTarget(employeeId);
              fileRef.current?.click();
            }}
            onStatus={(employeeId, status, leave) => void onPersonStatus(employeeId, status, leave)}
            onAddToPipeline={(employeeId) => void addToPipeline(employeeId)}
          />
        ) : null}

        {tab === "already" ? (
          <Card>
            <CardHeader>
              <CardTitle>{t("tabAlready")}</CardTitle>
              <CardDescription>{t("alreadyLead")}</CardDescription>
            </CardHeader>
            <CardContent>
              {alreadyBenefiting.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("alreadyEmpty")}</p>
              ) : (
                <EmployeeTable
                  people={alreadyBenefiting}
                  tw={tw}
                  contractLabel={t("contractCol")}
                />
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
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={busy || uploadRows !== null}
                  onClick={() => batchRef.current?.click()}
                >
                  {tw("people.batchUpload")}
                </Button>
                {batchNote ? <p className="text-sm text-muted-foreground">{batchNote}</p> : null}
              </div>
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
                              disabled={busy || uploadRows !== null}
                              onClick={() => {
                                setUploadTarget(person.id);
                                fileRef.current?.click();
                              }}
                            >
                              {person.has_contract ? tw("people.reupload") : tw("people.upload")}
                            </Button>
                            {person.has_contract && person.document_id ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="ml-2"
                                disabled={busy || uploadRows !== null}
                                onClick={() => {
                                  if (person.document_id) {
                                    void onShow(person.id, person.document_id);
                                  }
                                }}
                              >
                                {tw("people.show")}
                              </Button>
                            ) : null}
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
      <input
        ref={batchRef}
        type="file"
        className="sr-only"
        accept="application/pdf,.pdf"
        multiple
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) {
            void onBatch(files);
          }
        }}
      />
      {uploadRows ? (
        <ContractBatchModal
          rows={uploadRows}
          running={uploadRunning}
          onClose={(summary) => {
            setUploadRows(null);
            const note = tw("people.batchResult", {
              matched: String(summary.matched),
              unmatched: String(summary.unmatched),
              pending: String(summary.pending),
            });
            setBatchNote(
              summary.failed > 0
                ? `${note} ${tw("people.batchFailedCount", { failed: String(summary.failed) })}`
                : note,
            );
            if (summary.failed > 0 && summary.matched + summary.unmatched + summary.pending === 0) {
              setError(t("uploadFailed"));
            }
            void reload();
          }}
        />
      ) : null}
    </ShellPage>
  );
}

function RoundAction({
  label,
  children,
  disabled,
  onClick,
  href,
}: {
  label: string;
  children: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  href?: string;
}) {
  const className =
    "inline-flex size-8 items-center justify-center rounded-full border border-border bg-background text-foreground hover:bg-muted disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-3.5";
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          href ? (
            <Link href={href} aria-label={label} className={className} />
          ) : (
            <button
              type="button"
              aria-label={label}
              disabled={disabled}
              onClick={onClick}
              className={className}
            />
          )
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function StaffPeopleCard({
  companyId,
  people,
  establishments,
  establishmentId,
  onEstablishment,
  busyId,
  uploadsLocked,
  leaveById,
  onLeave,
  onShow,
  onUploadClick,
  onAddToPipeline,
  onStatus,
}: {
  companyId: string;
  people: PersonOut[];
  establishments: EstablishmentOut[];
  establishmentId: string;
  onEstablishment: (id: string) => void;
  busyId: string | null;
  uploadsLocked: boolean;
  leaveById: Record<string, (typeof LEAVE_TYPES)[number]>;
  onLeave: (employeeId: string, leave: (typeof LEAVE_TYPES)[number]) => void;
  onShow: (employeeId: string, documentId: string) => void;
  onUploadClick: (employeeId: string) => void;
  onAddToPipeline: (employeeId: string) => void;
  onStatus: (
    employeeId: string,
    status: (typeof STATUSES)[number],
    leave?: (typeof LEAVE_TYPES)[number],
  ) => void;
}) {
  const t = useTranslations("admins.companyDetail");
  const tc = useTranslations("admins.cases");
  const tw = useTranslations("workspace");
  const format = useFormatter();
  const [filterModality, setFilterModality] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterFile, setFilterFile] = useState("all");
  const [filterBenefit, setFilterBenefit] = useState("all");
  const [nameQuery, setNameQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const filtered = useMemo(() => {
    return people.filter((row) => {
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
      if (filterBenefit === "on" && !row.already_on_ss_reduction) {
        return false;
      }
      if (filterBenefit === "off" && row.already_on_ss_reduction) {
        return false;
      }
      if (filterBenefit === "might" && row.benefit_outlook !== "might") {
        return false;
      }
      if (filterBenefit === "never" && row.benefit_outlook !== "never") {
        return false;
      }
      const query = foldName(nameQuery.trim());
      if (query && !foldName(row.display_name || tw("people.unnamed")).includes(query)) {
        return false;
      }
      return true;
    });
  }, [people, filterModality, filterStatus, filterFile, filterBenefit, nameQuery, tw]);

  const visible = useMemo(() => {
    const direction = sortDir === "asc" ? 1 : -1;
    if (sortKey === "age") {
      return [...filtered].sort((a, b) => {
        if (a.age == null && b.age == null) {
          return 0;
        }
        if (a.age == null) {
          return 1;
        }
        if (b.age == null) {
          return -1;
        }
        return direction * (a.age - b.age);
      });
    }
    if (sortKey === "start") {
      return [...filtered].sort((a, b) => {
        if (!a.contract_started_on && !b.contract_started_on) {
          return 0;
        }
        if (!a.contract_started_on) {
          return 1;
        }
        if (!b.contract_started_on) {
          return -1;
        }
        return direction * a.contract_started_on.localeCompare(b.contract_started_on);
      });
    }
    const label = (row: PersonOut): string => {
      if (sortKey === "name") {
        return row.display_name || tw("people.unnamed");
      }
      if (sortKey === "modality") {
        return modalityLabel(row.contract_modality, tw);
      }
      if (sortKey === "status") {
        return tw(`people.status.${row.status}`);
      }
      return row.has_contract ? reviewLabel(row.review_status, tw) : tw("people.noFile");
    };
    return [...filtered].sort(
      (a, b) => direction * label(a).localeCompare(label(b), undefined, { sensitivity: "base" }),
    );
  }, [filtered, sortDir, sortKey, tw]);

  function onSort(column: SortKey) {
    if (sortKey === column) {
      setSortDir((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(column);
    setSortDir("asc");
  }

  const filtersActive =
    establishmentId !== "all" ||
    filterModality !== "all" ||
    filterStatus !== "all" ||
    filterFile !== "all" ||
    filterBenefit !== "all" ||
    nameQuery.trim() !== "";
  const showBenefit = visible.some((person) => person.term_benefit?.flagged);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("tabEmployees")}</CardTitle>
        <CardDescription className="text-xs">{t("benefitLead")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-1">
        <div className="flex flex-wrap items-end gap-3">
          <Field label={tw("people.search")} className="w-56">
            <Input
              value={nameQuery}
              onChange={(event) => setNameQuery(event.target.value)}
              placeholder={tw("people.searchPlaceholder")}
              aria-label={tw("people.search")}
            />
          </Field>
          {establishments.length >= 2 ? (
            <Field label={tw("people.filterEstablishment")} className="w-52">
              <Select
                value={establishmentId}
                onValueChange={(value) => {
                  if (value) {
                    onEstablishment(value);
                  }
                }}
                items={{
                  all: tw("people.filterAll"),
                  ...Object.fromEntries(
                    establishments.map((site) => [site.id, `${site.name} · ${site.ss_code}`]),
                  ),
                }}
              >
                <SelectTrigger aria-label={tw("people.filterEstablishment")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{tw("people.filterAll")}</SelectItem>
                  {establishments.map((site) => (
                    <SelectItem key={site.id} value={site.id}>
                      {site.name} · {site.ss_code}
                      {site.status === "CLOSED" ? ` (${tw("people.establishmentClosed")})` : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          ) : null}
          <Field label={tw("people.filterModality")} className="w-48">
            <Select
              value={filterModality}
              onValueChange={(value) => value && setFilterModality(value)}
              items={{
                all: tw("people.filterAll"),
                SEM_TERMO: tw("people.modality.SEM_TERMO"),
                TERMO_CERTO: tw("people.modality.TERMO_CERTO"),
                TERMO_INCERTO: tw("people.modality.TERMO_INCERTO"),
                OTHER: tw("people.modality.OTHER"),
                missing: tw("people.modalityUnknown"),
              }}
            >
              <SelectTrigger aria-label={tw("people.filterModality")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tw("people.filterAll")}</SelectItem>
                {MODALITIES.map((item) => (
                  <SelectItem key={item} value={item}>
                    {tw(`people.modality.${item}`)}
                  </SelectItem>
                ))}
                <SelectItem value="missing">{tw("people.modalityUnknown")}</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label={tw("people.filterStatus")} className="w-40">
            <Select
              value={filterStatus}
              onValueChange={(value) => value && setFilterStatus(value)}
              items={{
                all: tw("people.filterAll"),
                ACTIVE: tw("people.status.ACTIVE"),
                ON_LEAVE: tw("people.status.ON_LEAVE"),
                TERMINATED: tw("people.status.TERMINATED"),
              }}
            >
              <SelectTrigger aria-label={tw("people.filterStatus")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tw("people.filterAll")}</SelectItem>
                {STATUSES.map((status) => (
                  <SelectItem key={status} value={status}>
                    {tw(`people.status.${status}`)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={tw("people.filterFile")} className="w-44">
            <Select
              value={filterFile}
              onValueChange={(value) => value && setFilterFile(value)}
              items={{
                all: tw("people.filterAll"),
                missing: tw("people.filterMissingFile"),
                onFile: tw("people.filterOnFile"),
              }}
            >
              <SelectTrigger aria-label={tw("people.filterFile")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tw("people.filterAll")}</SelectItem>
                <SelectItem value="missing">{tw("people.filterMissingFile")}</SelectItem>
                <SelectItem value="onFile">{tw("people.filterOnFile")}</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label={tw("people.filterBenefit")} className="w-60">
            <Select
              value={filterBenefit}
              onValueChange={(value) => value && setFilterBenefit(value)}
              items={{
                all: tw("people.filterAll"),
                on: tw("people.filterBenefitOn"),
                off: tw("people.filterBenefitOff"),
                might: t("filterBenefitMight"),
                never: t("filterBenefitNever"),
              }}
            >
              <SelectTrigger aria-label={tw("people.filterBenefit")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{tw("people.filterAll")}</SelectItem>
                <SelectItem value="on">{tw("people.filterBenefitOn")}</SelectItem>
                <SelectItem value="off">{tw("people.filterBenefitOff")}</SelectItem>
                <SelectItem value="might">{t("filterBenefitMight")}</SelectItem>
                <SelectItem value="never">{t("filterBenefitNever")}</SelectItem>
              </SelectContent>
            </Select>
          </Field>
        </div>
        {people.length === 0 && !filtersActive ? (
          <p className="text-sm text-muted-foreground">{tw("people.empty")}</p>
        ) : visible.length === 0 ? (
          <p className="text-sm text-muted-foreground">{tw("people.filterEmpty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted-foreground">
                <tr className="border-b">
                  <SortHeader
                    label={tw("people.colName")}
                    column="name"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  <SortHeader
                    label={t("colAge")}
                    column="age"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  <SortHeader
                    label={t("colContractStart")}
                    column="start"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  <SortHeader
                    label={tw("people.colModality")}
                    column="modality"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  <SortHeader
                    label={tw("people.statusLabel")}
                    column="status"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  <SortHeader
                    label={tw("people.colFile")}
                    column="file"
                    sortKey={sortKey}
                    sortDir={sortDir}
                    onSort={onSort}
                  />
                  {showBenefit ? (
                    <th className="py-2 pr-3 font-medium">{t("benefitCol")}</th>
                  ) : null}
                  <th className="py-2 font-medium">{tw("people.colActions")}</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr key={row.id} className="border-b border-border/60 last:border-0">
                    <td className="py-2 pr-3 align-top">
                      {filterBenefit === "never" && row.benefit_block ? (
                        <Tooltip>
                          <TooltipTrigger className="cursor-help text-left font-medium underline decoration-dotted underline-offset-4">
                            {row.display_name || tw("people.unnamed")}
                          </TooltipTrigger>
                          <TooltipContent className="max-w-sm whitespace-normal text-left">
                            {blockMessage(row.benefit_block, t, format)}
                          </TooltipContent>
                        </Tooltip>
                      ) : (
                        <Link
                          href={paths.adminsEmployee(companyId, row.id)}
                          className="font-medium hover:underline"
                        >
                          {row.display_name || tw("people.unnamed")}
                        </Link>
                      )}
                      <div className="text-xs text-muted-foreground">
                        {sourceLabel(row.status_source, tw)}
                      </div>
                      {row.has_source_conflict ? (
                        <div className="text-xs text-destructive">{tw("people.conflict")}</div>
                      ) : null}
                      {row.already_on_ss_reduction ? (
                        <div className="text-xs text-muted-foreground">
                          {tw("people.alreadyBenefiting")}
                        </div>
                      ) : null}
                    </td>
                    <td className="py-2 pr-3 align-top tabular-nums">
                      {row.age == null ? t("ageUnknown") : row.age}
                    </td>
                    <td className="py-2 pr-3 align-top">
                      {row.contract_started_on
                        ? format.dateTime(new Date(`${row.contract_started_on}T00:00:00`), {
                            dateStyle: "medium",
                          })
                        : t("ageUnknown")}
                    </td>
                    <td className="py-2 pr-3 align-top">
                      {modalityLabel(row.contract_modality, tw)}
                    </td>
                    <td className="py-2 pr-3 align-top">
                      <div className="flex flex-col gap-2">
                        <Select
                          value={row.status}
                          disabled={busyId === row.id}
                          onValueChange={(value) => {
                            if (value) {
                              onStatus(row.id, value as (typeof STATUSES)[number]);
                            }
                          }}
                          items={Object.fromEntries(
                            STATUSES.map((status) => [status, tw(`people.status.${status}`)]),
                          )}
                        >
                          <SelectTrigger className="w-36" aria-label={tw("people.statusLabel")}>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {STATUSES.map((status) => (
                              <SelectItem key={status} value={status}>
                                {tw(`people.status.${status}`)}
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
                              onLeave(row.id, leave);
                              onStatus(row.id, "ON_LEAVE", leave);
                            }}
                            items={Object.fromEntries(
                              LEAVE_TYPES.map((leave) => [leave, tw(`people.leave.${leave}`)]),
                            )}
                          >
                            <SelectTrigger className="w-36" aria-label={tw("people.leaveLabel")}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {LEAVE_TYPES.map((leave) => (
                                <SelectItem key={leave} value={leave}>
                                  {tw(`people.leave.${leave}`)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : null}
                      </div>
                    </td>
                    <td className="py-2 pr-3 align-top">
                      {row.has_contract ? (
                        reviewLabel(row.review_status, tw)
                      ) : (
                        <span className="text-destructive">{tw("people.noFile")}</span>
                      )}
                    </td>
                    {showBenefit ? (
                      <td className="py-2 pr-3 align-top text-xs text-muted-foreground">
                        {row.term_benefit?.flagged
                          ? benefitLines(row.term_benefit, t, format).map((line) => (
                              <div key={line}>{line}</div>
                            ))
                          : null}
                      </td>
                    ) : null}
                    <td className="py-2 align-top">
                      <div className="flex items-center gap-1">
                        <RoundAction
                          label={row.has_contract ? tw("people.reupload") : tw("people.upload")}
                          disabled={busyId === row.id || uploadsLocked}
                          onClick={() => onUploadClick(row.id)}
                        >
                          <Upload />
                        </RoundAction>
                        {row.has_contract && row.document_id ? (
                          <RoundAction
                            label={tw("people.show")}
                            disabled={uploadsLocked}
                            onClick={() => {
                              if (row.document_id) {
                                onShow(row.id, row.document_id);
                              }
                            }}
                          >
                            <Eye />
                          </RoundAction>
                        ) : null}
                        {row.request_case_stage ? (
                          <RoundAction
                            label={row.request_case_stage}
                            href={paths.adminsEmployee(companyId, row.id)}
                          >
                            <Columns3 />
                          </RoundAction>
                        ) : row.benefit_outlook === "might" ? (
                          <RoundAction
                            label={tc("addToPipeline")}
                            disabled={busyId === row.id}
                            onClick={() => onAddToPipeline(row.id)}
                          >
                            <UserPlus />
                          </RoundAction>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SortHeader({
  label,
  column,
  sortKey,
  sortDir,
  onSort,
}: {
  label: string;
  column: SortKey;
  sortKey: SortKey;
  sortDir: "asc" | "desc";
  onSort: (column: SortKey) => void;
}) {
  const tw = useTranslations("workspace");
  const active = sortKey === column;
  return (
    <th
      className="py-2 pr-3 font-medium"
      aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button
        type="button"
        className="inline-flex items-center gap-1 hover:text-foreground"
        aria-label={tw("people.sortColumn", { column: label })}
        onClick={() => onSort(column)}
      >
        {label}
        <span aria-hidden="true">{active ? (sortDir === "asc" ? "↑" : "↓") : "↕"}</span>
      </button>
    </th>
  );
}

function blockMessage(
  block: BenefitBlockOut,
  t: ReturnType<typeof useTranslations>,
  format: ReturnType<typeof useFormatter>,
): string {
  const day = (iso: string) =>
    format.dateTime(new Date(`${iso}T00:00:00`), { dateStyle: "medium" });
  const month = (iso: string) =>
    format.dateTime(new Date(`${iso}T00:00:00`), { month: "long", year: "numeric" });
  return t(`benefitBlock.${block.reason}`, {
    date: block.contract_started_on ? day(block.contract_started_on) : "",
    age: block.age_on_start ?? "",
    month: block.counted_to ? month(block.counted_to) : "",
    lastDay: block.last_day ? day(block.last_day) : "",
  });
}

function benefitLines(
  benefit: TermBenefitOut,
  t: ReturnType<typeof useTranslations>,
  format: ReturnType<typeof useFormatter>,
): string[] {
  const day = (iso: string) =>
    format.dateTime(new Date(`${iso}T00:00:00`), { dateStyle: "medium" });
  const lines = benefit.readings
    .filter((reading) => reading.can_benefit)
    .map((reading) =>
      t(`benefit.${reading.rule}`, { date: day(reading.deemed_on) }),
    );
  if (benefit.early_earliest && benefit.early_latest && benefit.early_suggested) {
    lines.push(
      t("benefit.early", {
        earliest: day(benefit.early_earliest),
        latest: day(benefit.early_latest),
        suggested: day(benefit.early_suggested),
      }),
    );
  }
  return lines;
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
  const t = useTranslations("admins.companyDetail");
  const format = useFormatter();
  const showBenefit = people.some((person) => person.term_benefit?.flagged);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr className="border-b">
            <th className="py-2 pr-3 font-medium">{tw("people.title")}</th>
            <th className="py-2 pr-3 font-medium">{tw("people.statusLabel")}</th>
            <th className="py-2 pr-3 font-medium">{contractLabel}</th>
            {showBenefit ? (
              <th className="py-2 font-medium">{t("benefitCol")}</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={person.id} className="border-b border-border/60 last:border-0">
              <td className="py-2 pr-3 font-medium">
                {person.display_name || tw("people.unnamed")}
                {person.already_on_ss_reduction ? (
                  <div className="text-xs font-normal text-muted-foreground">
                    {tw("people.alreadyBenefiting")}
                  </div>
                ) : null}
              </td>
              <td className="py-2 pr-3">
                {person.status === "ACTIVE"
                  ? tw("people.status.ACTIVE")
                  : person.status === "ON_LEAVE"
                    ? tw("people.status.ON_LEAVE")
                    : tw("people.status.TERMINATED")}
              </td>
              <td className="py-2 pr-3 text-muted-foreground">
                {reviewLabel(person.review_status, tw)}
              </td>
              {showBenefit ? (
                <td className="py-2 text-xs text-muted-foreground">
                  {person.term_benefit?.flagged
                    ? benefitLines(person.term_benefit, t, format).map((line) => (
                        <div key={line}>{line}</div>
                      ))
                    : null}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
