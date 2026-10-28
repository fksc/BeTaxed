"use client";

import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { GripVertical, Undo2 } from "lucide-react";

import { MinutaWizard } from "@/components/admins/minuta-wizard";
import { DatePicker } from "@/components/ui/date-picker";
import { Input } from "@/components/ui/input";
import { CaseHistory } from "@/components/case-history";
import { Button } from "@/components/ui/button";
import { Link } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  listMinutaTemplates,
  listPipeline,
  listRejectionReasons,
  listRequestCases,
  runRequestOperation,
  uploadRequestFile,
} from "@/lib/api/workspace-client";
import type {
  MinutaTemplateOut,
  PipelineStageOut,
  RejectionReasonOut,
  RequestCaseOut,
  RequestMove,
} from "@/lib/api/workspace";
import { currentIdToken } from "@/lib/firebase";

const STAGE_TYPES = ["WORK", "WAIT_CLIENT", "WAIT_SS", "CLOSE_WON", "CLOSE_LOST"] as const;

function stageTypeLabel(type: string, t: (key: string) => string): string {
  if ((STAGE_TYPES as readonly string[]).includes(type)) {
    return t(`stageType.${type}`);
  }
  return type;
}

function stageTone(type: string): string {
  if (type === "WAIT_CLIENT") {
    return "bg-amber-100 text-amber-950";
  }
  if (type === "WAIT_SS") {
    return "bg-sky-100 text-sky-950";
  }
  if (type === "CLOSE_WON") {
    return "bg-emerald-100 text-emerald-950";
  }
  if (type === "CLOSE_LOST") {
    return "bg-rose-100 text-rose-950";
  }
  return "bg-muted text-foreground";
}

function pathLabel(path: string, t: (key: string) => string): string {
  if (path === "FIXED_TERM") {
    return t("pathFixed");
  }
  if (path === "OPEN_CONTRACT") {
    return t("pathOpen");
  }
  return path;
}

function stageAge(iso: string, locale: string): string {
  const elapsed = Date.now() - new Date(iso).getTime();
  if (!Number.isFinite(elapsed)) {
    return "";
  }
  const minutes = Math.max(0, Math.floor(elapsed / 60000));
  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });
  if (minutes < 60) {
    return rtf.format(-minutes, "minute");
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    return rtf.format(-hours, "hour");
  }
  return rtf.format(-Math.floor(hours / 24), "day");
}

export function RequestPipeline({ fixedCompanyId }: { fixedCompanyId?: string }) {
  const t = useTranslations("admins.cases");
  const locale = useLocale();
  const [stages, setStages] = useState<PipelineStageOut[]>([]);
  const [rows, setRows] = useState<RequestCaseOut[]>([]);
  const [templates, setTemplates] = useState<MinutaTemplateOut[]>([]);
  const [reasons, setReasons] = useState<RejectionReasonOut[]>([]);
  const [companies, setCompanies] = useState<[string, string][]>([]);
  const [companyId, setCompanyId] = useState(fixedCompanyId ?? "all");
  const [layout, setLayout] = useState<"board" | "table">("board");
  const [sort, setSort] = useState<"opened" | "company" | "stage">("opened");
  const [dragCaseId, setDragCaseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [openRowId, setOpenRowId] = useState<string | null>(null);
  const dragRef = useRef<string | null>(null);
  const [pending, setPending] = useState<{
    row: RequestCaseOut;
    move: RequestMove;
    stageName: string;
  } | null>(null);

  async function reload(nextCompany = fixedCompanyId ?? companyId) {
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("needAuth"));
      return;
    }
    const opts = { idToken };
    const [board, cases, minuta, rejection] = await Promise.all([
      listPipeline(opts),
      listRequestCases(opts, nextCompany === "all" ? null : nextCompany),
      listMinutaTemplates(opts),
      listRejectionReasons(opts),
    ]);
    setStages(board);
    setRows(cases);
    setTemplates(minuta);
    setReasons(rejection);
    if (nextCompany === "all") {
      const seen = new Map<string, string>();
      for (const row of cases) {
        seen.set(row.company_id, row.company_name);
      }
      setCompanies([...seen.entries()]);
    }
    setError(null);
  }

  useEffect(() => {
    void reload(fixedCompanyId ?? "all").catch(() => setError(t("needAuth")));
  }, [t, fixedCompanyId]);

  async function act(row: RequestCaseOut, code: string, payload: Record<string, unknown>) {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    setBusyId(row.id);
    try {
      await runRequestOperation(row.id, code, payload, { idToken });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("actionFailed"));
    } finally {
      setBusyId(null);
    }
  }

  const companyItems = {
    all: t("allCompanies"),
    ...Object.fromEntries(companies),
  };

  const ordered = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      if (sort === "company") {
        const byCompany = a.company_name.localeCompare(b.company_name, locale);
        if (byCompany !== 0) {
          return byCompany;
        }
        return (a.display_name ?? "").localeCompare(b.display_name ?? "", locale);
      }
      if (sort === "stage") {
        return new Date(a.stage_entered_at).getTime() - new Date(b.stage_entered_at).getTime();
      }
      return new Date(b.opened_at).getTime() - new Date(a.opened_at).getTime();
    });
    return copy;
  }, [rows, sort, locale]);

  function dropClass(stageId: string): string {
    if (!dragCaseId) {
      return "";
    }
    const row = rows.find((item) => item.id === dragCaseId);
    const allowed = row?.moves?.some((move) => move.stage_id === stageId);
    return allowed
      ? "border-primary bg-primary/10 ring-2 ring-primary/40"
      : "opacity-40";
  }

  function acceptsDrop(stageId: string): boolean {
    const caseId = dragRef.current;
    if (!caseId) {
      return false;
    }
    const row = rows.find((item) => item.id === caseId);
    return Boolean(row?.moves?.some((move) => move.stage_id === stageId));
  }

  function markOver(target: HTMLElement, on: boolean) {
    if (on) {
      target.dataset.over = "true";
    } else {
      delete target.dataset.over;
    }
  }

  async function onDropCard(caseId: string, stageId: string) {
    const row = rows.find((item) => item.id === caseId);
    const stage = stages.find((item) => item.id === stageId);
    const move = row?.moves?.find((item) => item.stage_id === stageId);
    if (!row || !stage || !move) {
      return;
    }
    if (
      move.operation === "REVERT" ||
      move.operation === "SEND_MINUTA" ||
      move.operation === "RECORD_FILING"
    ) {
      await act(row, move.operation, {});
      return;
    }
    if (move.operation === "RECORD_DECISION" && move.outcome === "favorable") {
      await act(row, move.operation, { outcome: "favorable" });
      return;
    }
    setPending({ row, move, stageName: stage.name });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        {fixedCompanyId ? null : (
          <label className="space-y-1 text-xs text-muted-foreground">
            <span className="block">{t("company")}</span>
            <Select
              value={companyId}
              items={companyItems}
              onValueChange={(value) => {
                if (!value) {
                  return;
                }
                setCompanyId(value);
                void reload(value).catch(() => setError(t("needAuth")));
              }}
            >
              <SelectTrigger className="w-56" aria-label={t("company")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("allCompanies")}</SelectItem>
                {companies.map(([id, name]) => (
                  <SelectItem key={id} value={id}>
                    {name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
        )}
        <label className="space-y-1 text-xs text-muted-foreground">
          <span className="block">{t("sort")}</span>
          <Select
            value={sort}
            items={{
              opened: t("sortOpened"),
              company: t("sortCompany"),
              stage: t("sortInStage"),
            }}
            onValueChange={(value) => {
              if (value === "opened" || value === "company" || value === "stage") {
                setSort(value);
              }
            }}
          >
            <SelectTrigger className="w-44" aria-label={t("sort")}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="opened">{t("sortOpened")}</SelectItem>
              <SelectItem value="company">{t("sortCompany")}</SelectItem>
              <SelectItem value="stage">{t("sortInStage")}</SelectItem>
            </SelectContent>
          </Select>
        </label>
        <Button
          type="button"
          size="sm"
          variant={layout === "board" ? "default" : "outline"}
          onClick={() => setLayout("board")}
        >
          {t("board")}
        </Button>
        <Button
          type="button"
          size="sm"
          variant={layout === "table" ? "default" : "outline"}
          onClick={() => setLayout("table")}
        >
          {t("tableView")}
        </Button>
      </div>
      {layout === "board" ? (
        <p className="text-xs text-muted-foreground">{t("dragHint")}</p>
      ) : null}
      {pending ? (
        <DropDetails
          pending={pending}
          reasons={reasons}
          busy={busyId === pending.row.id}
          onCancel={() => setPending(null)}
          onAct={async (row, code, payload) => {
            await act(row, code, payload);
            setPending(null);
          }}
        />
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">{t("pipelineEmpty")}</p> : null}
      {layout === "table" ? (
        <div className="overflow-hidden rounded-lg border border-border bg-card">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">{t("person")}</th>
                {fixedCompanyId ? null : (
                  <th className="px-3 py-2 font-medium">{t("company")}</th>
                )}
                <th className="px-3 py-2 font-medium">{t("stage")}</th>
                <th className="px-3 py-2 font-medium">{t("path")}</th>
                <th className="px-3 py-2 font-medium">{t("filed")}</th>
                <th className="px-3 py-2 font-medium">{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((row) => {
                const revert = row.moves?.find((move) => move.operation === "REVERT");
                const open = openRowId === row.id;
                return (
                  <Fragment key={row.id}>
                    <tr className="border-t border-border/70">
                      <td className="px-3 py-3 font-medium">
                        <Link
                          href={paths.adminsEmployee(row.company_id, row.employee_id)}
                          className="hover:underline"
                        >
                          {row.display_name || t("unnamed")}
                        </Link>
                        {row.remaining_months != null ? (
                          <div className="text-xs font-normal text-muted-foreground">
                            {t("remaining", { count: row.remaining_months })}
                          </div>
                        ) : null}
                      </td>
                      {fixedCompanyId ? null : (
                        <td className="px-3 py-3">
                          <Link
                            href={paths.adminsCompany(row.company_id)}
                            className="text-primary underline-offset-4 hover:underline"
                          >
                            {row.company_name}
                          </Link>
                        </td>
                      )}
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${stageTone(row.stage_type)}`}
                        >
                          {row.stage_name}
                        </span>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {stageTypeLabel(row.stage_type, t)}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground" title={t("inStage")}>
                          {stageAge(row.stage_entered_at, locale)}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-muted-foreground">{pathLabel(row.path, t)}</td>
                      <td className="px-3 py-3 text-muted-foreground">{row.applied_on || "—"}</td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-2">
                          {revert ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={busyId === row.id}
                              onClick={() => void act(row, "REVERT", {})}
                            >
                              <Undo2 />
                              {t("moveBack")}
                            </Button>
                          ) : null}
                          <Button
                            type="button"
                            size="sm"
                            variant={open ? "default" : "outline"}
                            onClick={() => setOpenRowId(open ? null : row.id)}
                          >
                            {open ? t("hideWork") : t("openWork")}
                          </Button>
                        </div>
                      </td>
                    </tr>
                    {open ? (
                      <tr key={`${row.id}-work`} className="border-t border-border/40 bg-muted/20">
                        <td className="px-3 py-3" colSpan={fixedCompanyId ? 5 : 6}>
                          <CaseActions
                            row={row}
                            templates={templates}
                            reasons={reasons}
                            busy={busyId === row.id}
                            onAct={act}
                            onChanged={() => reload()}
                          />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {stages.map((stage) => (
            <div
              key={stage.id}
              className={cn(
                "w-72 shrink-0 rounded-lg border border-border bg-muted/30 transition-opacity data-[over=true]:border-primary data-[over=true]:bg-primary/5 data-[over=true]:ring-2 data-[over=true]:ring-primary/30",
                dropClass(stage.id),
              )}
              onDragOver={(event) => {
                if (!acceptsDrop(stage.id)) {
                  return;
                }
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                markOver(event.currentTarget, true);
              }}
              onDragLeave={(event) => {
                if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
                  return;
                }
                markOver(event.currentTarget, false);
              }}
              onDrop={(event) => {
                event.preventDefault();
                markOver(event.currentTarget, false);
                const caseId = event.dataTransfer.getData("text/plain") || dragRef.current;
                dragRef.current = null;
                setDragCaseId(null);
                if (caseId) {
                  void onDropCard(caseId, stage.id);
                }
              }}
            >
              <div className="border-b border-border px-3 py-2">
                <div className="text-sm font-medium">{stage.name}</div>
                <div className="text-xs text-muted-foreground">
                  {stageTypeLabel(stage.stage_type, t)}
                </div>
              </div>
              <div className="min-h-28 space-y-2 p-2">
                {ordered
                  .filter((row) => row.stage_id === stage.id)
                  .map((row) => {
                    const revert = row.moves?.find((move) => move.operation === "REVERT");
                    return (
                      <div
                        key={row.id}
                        className="rounded-md border border-border bg-background p-2 text-sm shadow-sm"
                      >
                        <div className="flex items-start gap-1">
                          <div
                            draggable={busyId !== row.id && Boolean(row.moves?.length)}
                            className="mt-0.5 cursor-grab text-muted-foreground active:cursor-grabbing"
                            aria-label={t("dragHandle")}
                            onDragStart={(event) => {
                              dragRef.current = row.id;
                              setDragCaseId(row.id);
                              event.dataTransfer.setData("text/plain", row.id);
                              event.dataTransfer.effectAllowed = "move";
                            }}
                            onDragEnd={() => {
                              dragRef.current = null;
                              setDragCaseId(null);
                            }}
                          >
                            <GripVertical size={16} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <Link
                              href={paths.adminsEmployee(row.company_id, row.employee_id)}
                              className="font-medium hover:underline"
                            >
                              {row.display_name || t("unnamed")}
                            </Link>
                            {fixedCompanyId ? null : (
                              <Link
                                href={paths.adminsCompany(row.company_id)}
                                className="block truncate text-xs text-primary underline-offset-4 hover:underline"
                              >
                                {row.company_name}
                              </Link>
                            )}
                            <div className="text-xs text-muted-foreground">{pathLabel(row.path, t)}</div>
                            <div className="text-xs text-muted-foreground" title={t("inStage")}>
                              {stageAge(row.stage_entered_at, locale)}
                            </div>
                            {row.remaining_months != null ? (
                              <div className="text-xs text-muted-foreground">
                                {t("remaining", { count: row.remaining_months })}
                              </div>
                            ) : null}
                          </div>
                          {revert ? (
                            <Button
                              type="button"
                              size="icon"
                              variant="ghost"
                              aria-label={t("moveBack")}
                              disabled={busyId === row.id}
                              onClick={() => void act(row, "REVERT", {})}
                            >
                              <Undo2 />
                            </Button>
                          ) : null}
                        </div>
                        <div className="mt-2 border-t border-border/60 pt-2">
                          <CaseActions
                            row={row}
                            templates={templates}
                            reasons={reasons}
                            busy={busyId === row.id}
                            onAct={act}
                            onChanged={() => reload()}
                          />
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CaseActions({
  row,
  templates,
  reasons,
  busy,
  onAct,
  onChanged,
}: {
  row: RequestCaseOut;
  templates: MinutaTemplateOut[];
  reasons: RejectionReasonOut[];
  busy: boolean;
  onAct: (row: RequestCaseOut, code: string, payload: Record<string, unknown>) => Promise<void>;
  onChanged: () => Promise<void>;
}) {
  const t = useTranslations("admins.cases");
  const [reasonId, setReasonId] = useState(reasons[0]?.id ?? "");
  const [probationOn, setProbationOn] = useState("");
  const [appliedOn, setAppliedOn] = useState("");
  const [wizardOpen, setWizardOpen] = useState(false);
  const ops = row.operations ?? [];

  return (
    <div className="space-y-2">
      <CaseHistory events={row.events ?? []} />
      {ops.includes("RECORD_PROBATION") ? (
        <div className="space-y-1">
          <DatePicker
            value={probationOn}
            aria-label={t("probationEnd")}
            onChange={setProbationOn}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy || !probationOn}
            onClick={() =>
              void onAct(row, "RECORD_PROBATION", { probation_ends_on: probationOn })
            }
          >
            {t("recordProbation")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void onAct(row, "RECORD_PROBATION", { no_probation: true })}
          >
            {t("noProbation")}
          </Button>
        </div>
      ) : null}
      {ops.includes("GENERATE_MINUTA") ? (
        <>
          <Button type="button" size="sm" variant="outline" onClick={() => setWizardOpen(true)}>
            {t("prepareMinuta")}
          </Button>
          {wizardOpen ? (
            <MinutaWizard
              row={row}
              templates={templates}
              busy={busy}
              onClose={() => setWizardOpen(false)}
              onChanged={onChanged}
            />
          ) : null}
        </>
      ) : null}
      {ops.includes("ATTACH_SIGNED_SCAN") ? (
        <Input
          type="file"
          aria-label={t("attachScan")}
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) {
              return;
            }
            void (async () => {
              const idToken = await currentIdToken();
              if (!idToken) {
                return;
              }
              const stored = await uploadRequestFile(file, "SIGNED_MINUTA", row.company_id, {
                idToken,
              });
              await onAct(row, "ATTACH_SIGNED_SCAN", { file_id: stored.id });
            })();
          }}
        />
      ) : null}
      {ops.includes("RECORD_FILING") ? (
        <div className="space-y-1">
          <DatePicker
            value={appliedOn}
            aria-label={t("appliedOn")}
            onChange={setAppliedOn}
          />
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() =>
              void onAct(row, "RECORD_FILING", appliedOn ? { applied_on: appliedOn } : {})
            }
          >
            {t("recordFiling")}
          </Button>
        </div>
      ) : null}
      {ops.includes("RECORD_DECISION") ? (
        <DecisionForm
          row={row}
          reasons={reasons}
          reasonId={reasonId}
          busy={busy}
          onReason={setReasonId}
          onAct={onAct}
        />
      ) : null}
    </div>
  );
}

function DecisionForm({
  row,
  reasons,
  reasonId,
  busy,
  onReason,
  onAct,
}: {
  row: RequestCaseOut;
  reasons: RejectionReasonOut[];
  reasonId: string;
  busy: boolean;
  onReason: (id: string) => void;
  onAct: (row: RequestCaseOut, code: string, payload: Record<string, unknown>) => Promise<void>;
}) {
  const t = useTranslations("admins.cases");
  const [noticeId, setNoticeId] = useState<string | null>(row.notice_file_id);
  const reason = reasons.find((item) => item.id === reasonId);
  const claimBlocked = reason?.blocks_claim ?? true;

  return (
    <div className="space-y-1">
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy}
        onClick={() => void onAct(row, "RECORD_DECISION", { outcome: "favorable" })}
      >
        {t("favorable")}
      </Button>
      <Select
        value={reasonId}
        items={Object.fromEntries(reasons.map((item) => [item.id, item.label]))}
        onValueChange={(value) => value && onReason(value)}
      >
        <SelectTrigger aria-label={t("reason")}>
          <SelectValue placeholder={t("reason")} />
        </SelectTrigger>
        <SelectContent>
          {reasons.map((item) => (
            <SelectItem key={item.id} value={item.id}>
              {item.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Input
        type="file"
        aria-label={t("notice")}
        disabled={busy}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (!file) {
            return;
          }
          void (async () => {
            const idToken = await currentIdToken();
            if (!idToken) {
              return;
            }
            const stored = await uploadRequestFile(file, "UNFAVORABLE_NOTICE", row.company_id, {
              idToken,
            });
            setNoticeId(stored.id);
          })();
        }}
      />
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy || !reasonId || !noticeId}
        onClick={() =>
          void onAct(row, "RECORD_DECISION", {
            outcome: "unfavorable",
            rejection_reason_id: reasonId,
            file_id: noticeId,
          })
        }
      >
        {t("unfavorable")}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={busy || !row.can_claim || claimBlocked || !reasonId || !noticeId}
        onClick={() =>
          void onAct(row, "RECORD_DECISION", {
            outcome: "claim",
            rejection_reason_id: reasonId,
            file_id: noticeId,
          })
        }
      >
        {t("claim")}
      </Button>
    </div>
  );
}

function DropDetails({
  pending,
  reasons,
  busy,
  onCancel,
  onAct,
}: {
  pending: { row: RequestCaseOut; move: RequestMove; stageName: string };
  reasons: RejectionReasonOut[];
  busy: boolean;
  onCancel: () => void;
  onAct: (row: RequestCaseOut, code: string, payload: Record<string, unknown>) => Promise<void>;
}) {
  const t = useTranslations("admins.cases");
  const { row, move } = pending;
  const [probationOn, setProbationOn] = useState("");
  const [reasonId, setReasonId] = useState(reasons[0]?.id ?? "");
  const reason = reasons.find((item) => item.id === reasonId);
  const reasonItems = Object.fromEntries(reasons.map((item) => [item.id, item.label]));

  return (
    <div className="space-y-2 rounded-md border border-border bg-card p-3">
      <div className="text-sm font-medium">
        {t("dropNeeds")}: {row.display_name || t("unnamed")} → {pending.stageName}
      </div>
      {move.operation === "RECORD_PROBATION" ? (
        <div className="flex flex-wrap items-center gap-2">
          <DatePicker
            value={probationOn}
            aria-label={t("probationEnd")}
            onChange={setProbationOn}
            className="w-44"
          />
          <Button
            type="button"
            size="sm"
            disabled={busy || !probationOn}
            onClick={() =>
              void onAct(row, "RECORD_PROBATION", { probation_ends_on: probationOn })
            }
          >
            {t("recordProbation")}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => void onAct(row, "RECORD_PROBATION", { no_probation: true })}
          >
            {t("noProbation")}
          </Button>
        </div>
      ) : null}
      {move.operation === "ATTACH_SIGNED_SCAN" ? (
        <Input
          type="file"
          aria-label={t("attachScan")}
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) {
              return;
            }
            void (async () => {
              const idToken = await currentIdToken();
              if (!idToken) {
                return;
              }
              const stored = await uploadRequestFile(file, "SIGNED_MINUTA", row.company_id, {
                idToken,
              });
              await onAct(row, "ATTACH_SIGNED_SCAN", { file_id: stored.id });
            })();
          }}
        />
      ) : null}
      {move.operation === "RECORD_DECISION" && move.outcome !== "favorable" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={reasonId}
            items={reasonItems}
            onValueChange={(value) => value && setReasonId(value)}
          >
            <SelectTrigger className="w-72" aria-label={t("reason")}>
              <SelectValue placeholder={t("reason")} />
            </SelectTrigger>
            <SelectContent>
              {reasons.map((item) => (
                <SelectItem key={item.id} value={item.id}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            type="file"
            className="max-w-xs"
            aria-label={t("notice")}
            disabled={busy || !reasonId || (move.outcome === "claim" && reason?.blocks_claim)}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file || !reasonId) {
                return;
              }
              void (async () => {
                const idToken = await currentIdToken();
                if (!idToken) {
                  return;
                }
                const stored = await uploadRequestFile(
                  file,
                  "UNFAVORABLE_NOTICE",
                  row.company_id,
                  { idToken },
                );
                await onAct(row, "RECORD_DECISION", {
                  outcome: move.outcome,
                  rejection_reason_id: reasonId,
                  file_id: stored.id,
                });
              })();
            }}
          />
        </div>
      ) : null}
      <Button type="button" size="sm" variant="outline" onClick={onCancel}>
        {t("cancelDrop")}
      </Button>
    </div>
  );
}
