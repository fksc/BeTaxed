"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import LetterGlitch from "@/components/LetterGlitch";
import Stepper, { Step } from "@/components/Stepper";
import { Dropzone } from "@/components/intake/dropzone";
import { Field, TextInput } from "@/components/intake/field";
import { SavingsCard } from "@/components/intake/savings-card";
import { SsGuide } from "@/components/intake/ss-guide";
import { VerboseTable } from "@/components/intake/verbose-table";
import { PublicChrome } from "@/components/public/public-chrome";
import { Button } from "@/components/ui/button";
import { MonthPicker } from "@/components/ui/month-picker";
import {
  convertIntake,
  createIntake,
  declineIntake,
  getIntake,
  requestSalesCall,
  uploadSsFiles,
} from "@/lib/api/intakes";
import { ApiError, type IntakeOut } from "@/lib/api/types";
import { useRouter } from "@/i18n/navigation";
import { isVerboseUi } from "@/lib/dev-verbose";
import { currentIdToken, ensureEmailUser } from "@/lib/firebase";
import { saveCompanyId } from "@/lib/company-session";
import {
  clearIntakeSession,
  loadIntakeSession,
  saveIntakeSession,
  saveWorkspaceName,
} from "@/lib/intake-session";

type Phase = "flow" | "working" | "declined";
type CloseMode = "workspace" | "call";

function currentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function PassOne({ verboseUi = false }: { verboseUi?: boolean }) {
  const t = useTranslations();
  const router = useRouter();
  const showVerboseTable = verboseUi || isVerboseUi();
  const workingLines = t.raw("working.lines") as string[];
  const [phase, setPhase] = useState<Phase>("flow");
  const [step, setStep] = useState(1);
  const [booting, setBooting] = useState(() => loadIntakeSession() !== null);
  const [busy, setBusy] = useState(false);
  const [workingLine, setWorkingLine] = useState(workingLines[0]);
  const [error, setError] = useState<string | null>(null);
  const [confirmDecline, setConfirmDecline] = useState(false);
  const [intake, setIntake] = useState<IntakeOut | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [period, setPeriod] = useState(currentYearMonth);
  const [files, setFiles] = useState<File[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [legalName, setLegalName] = useState("");
  const [tradingName, setTradingName] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [closeMode, setCloseMode] = useState<CloseMode>("workspace");
  const [callName, setCallName] = useState("");
  const [callEmail, setCallEmail] = useState("");
  const [callPhone, setCallPhone] = useState("");
  const [callSent, setCallSent] = useState(false);

  function fail(error: unknown): string {
    if (error instanceof ApiError) {
      return error.message;
    }
    const code = (error as { code?: string }).code;
    if (code === "auth/invalid-credential" || code === "auth/wrong-password") {
      return t("errors.authInvalid");
    }
    if (code === "auth/weak-password") {
      return t("errors.authWeak");
    }
    if (code === "auth/invalid-email") {
      return t("errors.authEmail");
    }
    if (error instanceof Error) {
      return error.message;
    }
    return t("errors.generic");
  }

  useEffect(() => {
    const stored = loadIntakeSession();
    if (!stored) {
      return;
    }
    void (async () => {
      try {
        const idToken = await currentIdToken();
        setSignedIn(Boolean(idToken));
        const loaded = await getIntake(stored.intakeId, {
          sessionToken: stored.sessionToken,
          idToken,
        });
        setIntake(loaded);
        setSessionToken(stored.sessionToken);
        if (loaded.status === "CONVERTED") {
          router.replace("/companies/dashboard");
        } else if (loaded.teaser_now_monthly != null || loaded.teaser_potential_window != null) {
          setStep(3);
        }
      } catch {
        clearIntakeSession();
      } finally {
        setBooting(false);
      }
    })();
  }, [router]);

  useEffect(() => {
    if (!busy || phase !== "working") {
      return;
    }
    let i = 0;
    const timer = window.setInterval(() => {
      i = (i + 1) % workingLines.length;
      setWorkingLine(workingLines[i]);
    }, 1400);
    return () => window.clearInterval(timer);
  }, [busy, phase, workingLines]);

  async function authOpts() {
    return {
      sessionToken,
      idToken: await currentIdToken(),
    };
  }

  async function onUpload(event: React.FormEvent) {
    event.preventDefault();
    if (files.length === 0) {
      setError(t("errors.needFile"));
      return;
    }
    const started = performance.now();
    let nextStep = 2;
    setBusy(true);
    setPhase("working");
    setError(null);
    setWorkingLine(workingLines[0]);
    try {
      const idToken = await currentIdToken();
      let current = intake;
      let token = sessionToken;
      if (!current) {
        current = await createIntake({ idToken });
        token = current.session_token ?? null;
        saveIntakeSession(current.id, token);
        setSessionToken(token);
      }
      const uploaded = await uploadSsFiles(current.id, files, period, {
        sessionToken: token,
        idToken,
      });
      setIntake(uploaded);
      if (uploaded.latest_batch?.parse_status !== "APPLIED") {
        setError(uploaded.latest_batch?.parse_error || t("errors.parseFailed"));
      } else {
        nextStep = 3;
      }
    } catch (err) {
      setError(fail(err));
    } finally {
      const remain = 4000 - (performance.now() - started);
      if (remain > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, remain));
      }
      setStep(nextStep);
      setPhase("flow");
      setBusy(false);
    }
  }

  async function onContinue(event: React.FormEvent) {
    event.preventDefault();
    if (!intake) {
      return;
    }
    if (!legalName.trim()) {
      setError(t("errors.needLegalName"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let idToken = await currentIdToken();
      if (!idToken) {
        if (!email || !password) {
          setError(t("errors.needAuthContinue"));
          setBusy(false);
          return;
        }
        await ensureEmailUser(email, password);
        idToken = await currentIdToken();
        setSignedIn(true);
      }
      const converted = await convertIntake(
        intake.id,
        legalName.trim(),
        tradingName.trim() || null,
        { sessionToken, idToken },
      );
      setIntake(converted);
      saveWorkspaceName(legalName.trim());
      if (converted.company_id) {
        saveCompanyId(converted.company_id);
      }
      saveIntakeSession(converted.id, null);
      setSessionToken(null);
      router.replace("/companies/dashboard");
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  }

  async function onSalesCall(event: React.FormEvent) {
    event.preventDefault();
    if (!intake) {
      return;
    }
    if (!callName.trim() || !callEmail.trim() || !callPhone.trim()) {
      setError(t("errors.needCall"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await requestSalesCall(
        intake.id,
        {
          name: callName.trim(),
          email: callEmail.trim(),
          phone: callPhone.trim(),
        },
        await authOpts(),
      );
      setCallSent(true);
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  }

  async function onDecline() {
    if (!intake) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await declineIntake(intake.id, await authOpts());
      clearIntakeSession();
      setIntake(null);
      setSessionToken(null);
      setConfirmDecline(false);
      setCallSent(false);
      setPhase("declined");
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    clearIntakeSession();
    setIntake(null);
    setSessionToken(null);
    setFiles([]);
    setConfirmDecline(false);
    setCallSent(false);
    setCloseMode("workspace");
    setPhase("flow");
    setStep(1);
    setError(null);
  }

  if (booting) {
    return <div className="min-h-svh" />;
  }

  return (
    <div className="flex min-h-full flex-col">
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-8 lg:py-12">
        <PublicChrome />
        {phase === "declined" ? (
          <section className="max-w-lg space-y-5">
            <h1 className="font-editorial text-4xl tracking-tight">
              {t("declined.headline")}
            </h1>
            <p className="text-lg text-muted-foreground">{t("declined.lead")}</p>
            <Button type="button" variant="outline" size="lg" onClick={reset}>
              {t("declined.again")}
            </Button>
          </section>
        ) : (
          <Stepper
            step={step}
            onStepChange={setStep}
            linear
            showFooter={false}
            theme="dark"
            accentColor="#88375c"
            width="100%"
            radius={28}
            indicator="numbers"
          >
            <Step title={t("start.stepBrief")}>
              <BriefStep onContinue={() => setStep(2)} />
            </Step>
            <Step title={t("start.stepUpload")}>
              <form className="mx-auto flex w-full max-w-xl flex-col gap-5" onSubmit={onUpload}>
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-2">
                    <p className="text-xs font-medium tracking-[0.16em] text-accent-ink uppercase">
                      {t("start.uploadKicker")}
                    </p>
                    <h2 className="font-editorial text-3xl tracking-tight">{t("start.uploadTitle")}</h2>
                  </div>
                  <SsGuide />
                </div>
                <div className="space-y-5">
                  {error && step === 2 ? <ErrorBanner message={error} /> : null}
                  <Field label={t("start.period")}>
                    <MonthPicker value={period} onChange={setPeriod} disabled={busy} />
                  </Field>
                  <Dropzone files={files} disabled={busy} onFiles={setFiles} />
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="button"
                      variant="outline"
                      size="lg"
                      className="h-11 sm:w-32"
                      disabled={busy}
                      onClick={() => setStep(1)}
                    >
                      {t("guide.back")}
                    </Button>
                    <Button type="submit" size="lg" className="h-11 flex-1" disabled={busy}>
                      {t("start.submit")}
                    </Button>
                  </div>
                </div>
              </form>
            </Step>
            <Step title={t("start.stepResult")}>
              {intake ? (
                <ResultView
                  intake={intake}
                  error={error}
                  busy={busy}
                  signedIn={signedIn}
                  email={email}
                  password={password}
                  legalName={legalName}
                  tradingName={tradingName}
                  confirmDecline={confirmDecline}
                  closeMode={closeMode}
                  callName={callName}
                  callEmail={callEmail}
                  callPhone={callPhone}
                  callSent={callSent}
                  setEmail={setEmail}
                  setPassword={setPassword}
                  setLegalName={setLegalName}
                  setTradingName={setTradingName}
                  setConfirmDecline={setConfirmDecline}
                  setCloseMode={setCloseMode}
                  setCallName={setCallName}
                  setCallEmail={setCallEmail}
                  setCallPhone={setCallPhone}
                  onContinue={onContinue}
                  onSalesCall={onSalesCall}
                  onDecline={() => void onDecline()}
                  showVerboseTable={showVerboseTable}
                />
              ) : (
                <p className="text-muted-foreground">{t("result.waiting")}</p>
              )}
            </Step>
          </Stepper>
        )}
      </main>
      {phase === "working" ? <WorkingOverlay line={workingLine} /> : null}
    </div>
  );
}

function BriefStep({ onContinue }: { onContinue: () => void }) {
  const t = useTranslations("start");
  const points = t.raw("points") as { title: string; body: string }[];
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8">
      <div className="space-y-4">
        <p className="text-xs font-medium tracking-[0.16em] text-accent-ink uppercase">
          {t("kicker")}
        </p>
        <h1 className="font-editorial text-4xl leading-[1.15] tracking-tight text-balance sm:text-5xl">
          {t("headline")}
        </h1>
        <p className="text-lg leading-relaxed text-muted-foreground">{t("lead")}</p>
      </div>
      <ol className="flex flex-col gap-4">
        {points.map((point) => (
          <li key={point.title} className="rounded-2xl border border-white/10 bg-background/30 p-4">
            <p className="font-medium">{point.title}</p>
            <p className="mt-1 leading-relaxed text-muted-foreground">{point.body}</p>
          </li>
        ))}
      </ol>
      <Button type="button" size="lg" className="h-11 w-full sm:w-fit sm:px-8" onClick={onContinue}>
        {t("continue")}
      </Button>
    </div>
  );
}

function ResultView({
  intake,
  error,
  busy,
  signedIn,
  email,
  password,
  legalName,
  tradingName,
  confirmDecline,
  closeMode,
  callName,
  callEmail,
  callPhone,
  callSent,
  setEmail,
  setPassword,
  setLegalName,
  setTradingName,
  setConfirmDecline,
  setCloseMode,
  setCallName,
  setCallEmail,
  setCallPhone,
  onContinue,
  onSalesCall,
  onDecline,
  showVerboseTable,
}: {
  intake: IntakeOut;
  error: string | null;
  busy: boolean;
  signedIn: boolean;
  email: string;
  password: string;
  legalName: string;
  tradingName: string;
  confirmDecline: boolean;
  closeMode: CloseMode;
  callName: string;
  callEmail: string;
  callPhone: string;
  callSent: boolean;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  setLegalName: (value: string) => void;
  setTradingName: (value: string) => void;
  setConfirmDecline: (value: boolean) => void;
  setCloseMode: (value: CloseMode) => void;
  setCallName: (value: string) => void;
  setCallEmail: (value: string) => void;
  setCallPhone: (value: string) => void;
  onContinue: (event: React.FormEvent) => void;
  onSalesCall: (event: React.FormEvent) => void;
  onDecline: () => void;
  showVerboseTable: boolean;
}) {
  const t = useTranslations();
  const model = t.raw("result.model") as string[];
  return (
    <div className="space-y-8">
      <div className="grid items-start gap-8 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-6">
          <SavingsCard intake={intake} />
          <div className="space-y-3">
            <h2 className="font-editorial text-2xl tracking-tight">{t("result.modelTitle")}</h2>
            <ul className="flex flex-col gap-3">
              {model.map((line) => (
                <li key={line} className="leading-relaxed text-muted-foreground">
                  {line}
                </li>
              ))}
            </ul>
          </div>
          <DeclineControl
            busy={busy}
            confirm={confirmDecline}
            onAsk={() => setConfirmDecline(true)}
            onCancel={() => setConfirmDecline(false)}
            onDecline={onDecline}
          />
        </div>

        <div className="rounded-3xl border border-border bg-card p-6 shadow-[0_12px_40px_oklch(0.22_0.02_250_/_0.06)]">
          <div className="mb-6 grid grid-cols-2 gap-2 rounded-2xl bg-muted p-1">
            <button
              type="button"
              className={tabClass(closeMode === "workspace")}
              onClick={() => setCloseMode("workspace")}
            >
              {t("result.workspaceTab")}
            </button>
            <button
              type="button"
              className={tabClass(closeMode === "call")}
              onClick={() => setCloseMode("call")}
            >
              {t("result.callTab")}
            </button>
          </div>

          {error ? <ErrorBanner message={error} /> : null}

          {closeMode === "workspace" ? (
            <form className="space-y-5" onSubmit={onContinue}>
              <div className="space-y-1">
                <p className="text-lg font-medium">{t("result.continueTitle")}</p>
                <p className="text-muted-foreground">{t("result.accountHint")}</p>
              </div>
              {!signedIn ? (
                <AuthFields
                  email={email}
                  password={password}
                  setEmail={setEmail}
                  setPassword={setPassword}
                />
              ) : null}
              <Field label={t("result.legalName")}>
                <TextInput
                  value={legalName}
                  onChange={(event) => setLegalName(event.target.value)}
                  required
                  disabled={busy}
                  autoComplete="organization"
                />
              </Field>
              <Field label={t("result.tradingName")} hint={t("result.optional")}>
                <TextInput
                  value={tradingName}
                  onChange={(event) => setTradingName(event.target.value)}
                  disabled={busy}
                />
              </Field>
              <Button type="submit" size="lg" className="h-11 w-full" disabled={busy}>
                {busy ? t("result.opening") : t("result.createWorkspace")}
              </Button>
            </form>
          ) : callSent ? (
            <div className="space-y-3">
              <p className="text-lg font-medium">{t("result.callDone")}</p>
              <p className="leading-relaxed text-muted-foreground">{t("result.callDoneLead")}</p>
              <Button type="button" variant="outline" onClick={() => setCloseMode("workspace")}>
                {t("result.workspaceTab")}
              </Button>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={onSalesCall}>
              <div className="space-y-1">
                <p className="text-lg font-medium">{t("result.callTitle")}</p>
                <p className="text-muted-foreground">{t("result.callLead")}</p>
              </div>
              <Field label={t("result.callName")}>
                <TextInput
                  value={callName}
                  onChange={(event) => setCallName(event.target.value)}
                  required
                  disabled={busy}
                  autoComplete="name"
                />
              </Field>
              <Field label={t("auth.email")}>
                <TextInput
                  type="email"
                  value={callEmail}
                  onChange={(event) => setCallEmail(event.target.value)}
                  required
                  disabled={busy}
                  autoComplete="email"
                />
              </Field>
              <Field label={t("result.callPhone")}>
                <TextInput
                  type="tel"
                  value={callPhone}
                  onChange={(event) => setCallPhone(event.target.value)}
                  required
                  disabled={busy}
                  autoComplete="tel"
                />
              </Field>
              <Button type="submit" size="lg" className="h-11 w-full" disabled={busy}>
                {busy ? t("result.callSending") : t("result.callSubmit")}
              </Button>
            </form>
          )}
        </div>
      </div>

      {showVerboseTable && intake.verbose_people?.length ? (
        <VerboseTable people={intake.verbose_people} />
      ) : null}
    </div>
  );
}

function tabClass(active: boolean): string {
  return active
    ? "rounded-xl bg-card px-3 py-2 text-sm font-medium"
    : "rounded-xl px-3 py-2 text-sm text-muted-foreground";
}

function DeclineControl({
  busy,
  confirm,
  onAsk,
  onCancel,
  onDecline,
}: {
  busy: boolean;
  confirm: boolean;
  onAsk: () => void;
  onCancel: () => void;
  onDecline: () => void;
}) {
  const t = useTranslations("result");
  if (!confirm) {
    return (
      <button
        type="button"
        className="text-left text-muted-foreground underline-offset-4 hover:underline"
        onClick={onAsk}
      >
        {t("decline")}
      </button>
    );
  }
  return (
    <div className="space-y-3 rounded-xl bg-muted p-4">
      <p>{t("declineConfirm")}</p>
      <div className="flex gap-2">
        <Button type="button" variant="destructive" disabled={busy} onClick={onDecline}>
          {t("declineYes")}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t("cancel")}
        </Button>
      </div>
    </div>
  );
}

function AuthFields({
  email,
  password,
  setEmail,
  setPassword,
}: {
  email: string;
  password: string;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
}) {
  const t = useTranslations("auth");
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t("email")}>
        <TextInput
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </Field>
      <Field label={t("password")}>
        <TextInput
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </Field>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <p className="mb-4 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-destructive">
      {message}
    </p>
  );
}

function WorkingOverlay({ line }: { line: string }) {
  return (
    <div className="fixed inset-0 z-50" style={{ backgroundColor: "#070608" }}>
      <LetterGlitch
        glitchColors={["#ffffff", "#88375c"]}
        baseColor="#ffffff"
        backgroundColor="#070608"
        glitchAmount={0.4}
        className="absolute inset-0 h-full w-full"
        style={{ backgroundColor: "#070608" }}
      />
      <div className="relative z-10 flex h-full items-end justify-center p-10 sm:items-center">
        <p
          className="max-w-xl rounded-3xl px-8 py-5 text-center font-editorial text-4xl tracking-tight text-balance sm:text-5xl"
          style={{ backgroundColor: "rgba(7, 6, 8, 0.72)", color: "#f4f1ec" }}
        >
          {line}
        </p>
      </div>
    </div>
  );
}
