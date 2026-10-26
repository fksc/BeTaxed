"use client";

import { useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { Link } from "@/i18n/navigation";
import {
  getOpsCompany,
  listPeople,
  listRequestCases,
  openPersonContract,
} from "@/lib/api/workspace-client";
import type { PersonOut, RequestCaseOut } from "@/lib/api/workspace";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";

export function OpsEmployeeDetailPage({
  companyId,
  employeeId,
}: {
  companyId: string;
  employeeId: string;
}) {
  const t = useTranslations("admins.employee");
  const tc = useTranslations("admins.companyDetail");
  const tw = useTranslations("workspace");
  const tk = useTranslations("admins.cases");
  const format = useFormatter();
  const [person, setPerson] = useState<PersonOut | null>(null);
  const [companyName, setCompanyName] = useState("");
  const [cases, setCases] = useState<RequestCaseOut[]>([]);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        setError(t("needAuth"));
        return;
      }
      try {
        const [company, people, requests] = await Promise.all([
          getOpsCompany(companyId, { idToken }),
          listPeople({ idToken, companyId }),
          listRequestCases({ idToken }, companyId),
        ]);
        if (cancelled) {
          return;
        }
        const match = people.find((row) => row.id === employeeId) ?? null;
        setCompanyName(company.legal_name);
        setPerson(match);
        setCases(requests.filter((row) => row.employee_id === employeeId));
        setMissing(match == null);
        setError(null);
      } catch {
        if (!cancelled) {
          setError(t("needAuth"));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [companyId, employeeId, t]);

  const day = (iso: string) =>
    format.dateTime(new Date(`${iso}T00:00:00`), { dateStyle: "medium" });

  return (
    <ShellPage crumb={person?.display_name || t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <Link
          href={`${paths.adminsCompany(companyId)}?tab=employees`}
          className="text-xs text-muted-foreground underline-offset-4 hover:underline"
        >
          {t("back")}
        </Link>
        <div className="text-base font-semibold">{person?.display_name || t("crumb")}</div>
        <Link
          href={paths.adminsCompany(companyId)}
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          {companyName}
        </Link>
      </div>
      <div className="space-y-4 p-4 sm:p-6">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {missing ? <p className="text-sm text-muted-foreground">{t("missing")}</p> : null}
        {person ? (
          <>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t("facts")}</CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
                <Fact label={t("age")} value={person.age == null ? "—" : String(person.age)} />
                <Fact
                  label={t("contractStart")}
                  value={person.contract_started_on ? day(person.contract_started_on) : "—"}
                />
                <Fact
                  label={t("modality")}
                  value={
                    person.contract_modality
                      ? tw(`people.modality.${person.contract_modality}`)
                      : tw("people.modalityUnknown")
                  }
                />
                <Fact label={t("status")} value={tw(`people.status.${person.status}`)} />
                <Fact
                  label={t("file")}
                  value={
                    !person.has_contract || !person.review_status
                      ? tw("people.noFile")
                      : person.review_status === "PENDING"
                        ? tw("people.pending")
                        : person.review_status === "FAILED"
                          ? tw("people.failed")
                          : tw("people.received")
                  }
                />
                {person.has_contract && person.document_id ? (
                  <div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const documentId = person.document_id;
                        if (!documentId) {
                          return;
                        }
                        void (async () => {
                          const idToken = await currentIdToken();
                          if (!idToken) {
                            return;
                          }
                          await openPersonContract(person.id, documentId, {
                            idToken,
                            companyId,
                          });
                        })();
                      }}
                    >
                      {t("showContract")}
                    </Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">{t("pipeline")}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {cases.length === 0 ? (
                  <p className="text-muted-foreground">{t("noCase")}</p>
                ) : (
                  cases.map((item) => (
                    <div key={item.id} className="rounded-md border border-border p-3">
                      <div className="font-medium">{item.stage_name}</div>
                      <div className="text-xs text-muted-foreground">
                        {stageTypeLabel(item.stage_type, tk)}
                      </div>
                      <div className="mt-2 text-muted-foreground">
                        {item.path === "FIXED_TERM" ? tk("pathFixed") : tk("pathOpen")}
                        {item.applied_on ? ` · ${t("filed")} ${day(item.applied_on)}` : ""}
                        {item.benefit_starts_on
                          ? ` · ${t("benefitStart")} ${day(item.benefit_starts_on)}`
                          : ""}
                        {item.remaining_months != null
                          ? ` · ${tk("remaining", { count: item.remaining_months })}`
                          : ""}
                      </div>
                    </div>
                  ))
                )}
                <Link
                  href={`${paths.adminsCompany(companyId)}?tab=pipeline`}
                  className="inline-block text-xs text-primary underline-offset-4 hover:underline"
                >
                  {tk("pipeline")}
                </Link>
              </CardContent>
            </Card>
            {person.term_benefit?.flagged ? (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{t("possible")}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm text-muted-foreground">
                  {person.term_benefit.readings
                    .filter((reading) => reading.can_benefit)
                    .map((reading) => (
                      <div key={reading.rule}>
                        {tc(`benefit.${reading.rule}`, { date: day(reading.deemed_on) })}
                      </div>
                    ))}
                  {person.term_benefit.early_earliest &&
                  person.term_benefit.early_latest &&
                  person.term_benefit.early_suggested ? (
                    <div>
                      {tc("benefit.early", {
                        earliest: day(person.term_benefit.early_earliest),
                        latest: day(person.term_benefit.early_latest),
                        suggested: day(person.term_benefit.early_suggested),
                      })}
                    </div>
                  ) : null}
                </CardContent>
              </Card>
            ) : null}
          </>
        ) : null}
      </div>
    </ShellPage>
  );
}

const STAGE_TYPES = ["WORK", "WAIT_CLIENT", "WAIT_SS", "CLOSE_WON", "CLOSE_LOST"] as const;

function stageTypeLabel(type: string, t: (key: string) => string): string {
  if ((STAGE_TYPES as readonly string[]).includes(type)) {
    return t(`stageType.${type}`);
  }
  return type;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div>{value}</div>
    </div>
  );
}
