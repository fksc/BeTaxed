"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { uploadContractFile, uploadPersonContractFile } from "@/lib/api/workspace-client";
import { ApiError } from "@/lib/api/types";

type Phase = "queued" | "uploading" | "matching" | "done" | "failed";

export type ContractUploadRow = {
  name: string;
  size: number;
  phase: Phase;
  percent: number;
  status: string | null;
};

export type ContractUploadSummary = {
  matched: number;
  unmatched: number;
  pending: number;
  failed: number;
};

function formatBytes(size: number): string {
  if (size < 1024) {
    return `${size} B`;
  }
  if (size < 1024 * 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function contractUploadRows(files: File[]): ContractUploadRow[] {
  return files.map((file) => ({
    name: file.name,
    size: file.size,
    phase: "queued",
    percent: 0,
    status: null,
  }));
}

export function summarizeContractUploads(rows: ContractUploadRow[]): ContractUploadSummary {
  return {
    matched: rows.filter((row) => row.status === "MATCHED").length,
    unmatched: rows.filter((row) => row.status === "UNMATCHED").length,
    pending: rows.filter((row) => row.status === "PENDING").length,
    failed: rows.filter((row) => row.phase === "failed").length,
  };
}

export async function runContractUploads(input: {
  files: File[];
  companyId: string;
  employeeId?: string;
  getIdToken: (forceRefresh?: boolean) => Promise<string | null>;
  onRows: (rows: ContractUploadRow[]) => void;
}): Promise<ContractUploadSummary> {
  const rows = contractUploadRows(input.files);
  input.onRows(rows.map((row) => ({ ...row })));

  function publish(index: number, next: Partial<ContractUploadRow>) {
    rows[index] = { ...rows[index], ...next };
    input.onRows(rows.map((row) => ({ ...row })));
  }

  async function send(file: File, index: number, forceRefresh: boolean) {
    const idToken = await input.getIdToken(forceRefresh);
    if (!idToken) {
      throw new ApiError("Missing bearer token.", 401);
    }
    const onProgress = (percent: number) => {
      publish(index, {
        phase: percent >= 100 ? "matching" : "uploading",
        percent,
      });
    };
    const job = input.employeeId
      ? uploadPersonContractFile(
          input.employeeId,
          file,
          { idToken, companyId: input.companyId },
          onProgress,
        )
      : uploadContractFile(file, { idToken, companyId: input.companyId }, onProgress);
    return job.promise;
  }

  for (let index = 0; index < input.files.length; index += 1) {
    const file = input.files[index];
    publish(index, { phase: "uploading", percent: 0 });
    try {
      let item;
      try {
        item = await send(file, index, false);
      } catch (err) {
        if (!(err instanceof ApiError) || err.status !== 401) {
          throw err;
        }
        item = await send(file, index, true);
      }
      const status = "status" in item ? item.status : item.review_status;
      publish(index, { phase: "done", percent: 100, status });
    } catch {
      publish(index, { phase: "failed", percent: 100 });
    }
  }
  return summarizeContractUploads(rows);
}

export function ContractBatchModal({
  rows,
  running,
  onClose,
}: {
  rows: ContractUploadRow[];
  running: boolean;
  onClose: (summary: ContractUploadSummary) => void;
}) {
  const t = useTranslations("workspace");
  const finished = rows.filter((row) => row.phase === "done" || row.phase === "failed").length;
  const current = rows.find((row) => row.phase === "uploading" || row.phase === "matching");
  const partial =
    current?.phase === "uploading" ? current.percent / 100 : current?.phase === "matching" ? 0.95 : 0;
  const overall = rows.length === 0 ? 0 : Math.round(((finished + partial) / rows.length) * 100);
  const summary = summarizeContractUploads(rows);

  function statusLine(row: ContractUploadRow): string {
    if (row.phase === "queued") {
      return t("people.batchWaiting");
    }
    if (row.phase === "uploading") {
      return t("people.batchUploading", { percent: String(row.percent) });
    }
    if (row.phase === "matching") {
      return t("people.batchMatching");
    }
    if (row.phase === "failed") {
      return t("people.batchFileFailed");
    }
    if (row.status === "MATCHED") {
      return t("people.batchLinked");
    }
    if (row.status === "UNMATCHED") {
      return t("people.batchUnmatched");
    }
    if (row.status === "PENDING") {
      return t("people.pending");
    }
    if (row.status === "FAILED") {
      return t("people.failed");
    }
    return t("people.received");
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 p-4 backdrop-blur-sm">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contract-batch-title"
        className="flex max-h-[min(40rem,calc(100vh-2rem))] w-full max-w-lg flex-col rounded-2xl border border-border bg-card shadow-lg"
      >
        <div className="space-y-3 border-b border-border px-5 py-4">
          <div className="flex items-baseline justify-between gap-3">
            <h2 id="contract-batch-title" className="text-base font-semibold">
              {running ? t("people.batchTitle") : t("people.batchTitleDone")}
            </h2>
            <p className="text-sm text-muted-foreground">
              {t("people.batchOverall", { done: String(finished), total: String(rows.length) })}
            </p>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full bg-primary transition-[width] duration-200 ${
                current?.phase === "matching" ? "animate-pulse" : ""
              }`}
              style={{ width: `${overall}%` }}
            />
          </div>
        </div>
        <ul className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {rows.map((row, index) => (
            <li key={`${row.name}-${index}`} className="space-y-1.5">
              <div className="flex items-baseline justify-between gap-3">
                <p className="truncate text-sm font-medium">{row.name}</p>
                <p className="shrink-0 text-xs text-muted-foreground">{formatBytes(row.size)}</p>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-[width] duration-200 ${
                    row.phase === "failed"
                      ? "bg-destructive"
                      : row.phase === "matching"
                        ? "animate-pulse bg-primary/70"
                        : "bg-primary"
                  }`}
                  style={{ width: `${row.phase === "queued" ? 0 : row.percent}%` }}
                />
              </div>
              <p
                className={`text-xs ${
                  row.phase === "failed" ? "text-destructive" : "text-muted-foreground"
                }`}
              >
                {statusLine(row)}
              </p>
            </li>
          ))}
        </ul>
        <div className="flex items-center justify-between gap-3 border-t border-border px-5 py-4">
          <p className="text-sm text-muted-foreground">
            {running
              ? t("people.batchWorking")
              : t("people.batchResult", {
                  matched: String(summary.matched),
                  unmatched: String(summary.unmatched),
                  pending: String(summary.pending),
                })}
            {!running && summary.failed > 0
              ? ` ${t("people.batchFailedCount", { failed: String(summary.failed) })}`
              : null}
          </p>
          <Button type="button" size="sm" disabled={running} onClick={() => onClose(summary)}>
            {t("people.batchClose")}
          </Button>
        </div>
      </div>
    </div>
  );
}
