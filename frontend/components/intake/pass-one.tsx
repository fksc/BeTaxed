"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Dropzone } from "@/components/intake/dropzone";
import { Field, TextInput } from "@/components/intake/field";
import { TeaserCards } from "@/components/intake/teaser-cards";
import { VerboseTable } from "@/components/intake/verbose-table";
import { Button } from "@/components/ui/button";
import {
  convertIntake,
  createIntake,
  declineIntake,
  getIntake,
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

type Path = "upload" | "account";
type Phase = "start" | "working" | "result" | "converted" | "declined";

function currentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function PassOne({ verboseUi = false }: { verboseUi?: boolean }) {
  const t = useTranslations();
  const router = useRouter();
  const showVerboseTable = verboseUi || isVerboseUi();
  const workingLines = t.raw("working.lines") as string[];
  const [path, setPath] = useState<Path>("upload");
  const [phase, setPhase] = useState<Phase>("start");
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
        } else if (loaded.teaser_now_monthly != null) {
          setPhase("result");
        }
      } catch {
        clearIntakeSession();
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
    setBusy(true);
    setPhase("working");
    setError(null);
    setWorkingLine(workingLines[0]);
    try {
      let idToken = await currentIdToken();
      if (path === "account") {
        if (!email || !password) {
          setError(t("errors.needAuthStart"));
          setPhase("start");
          setBusy(false);
          return;
        }
        await ensureEmailUser(email, password);
        idToken = await currentIdToken();
        setSignedIn(true);
      }
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
        setPhase("start");
        return;
      }
      setPhase("result");
    } catch (err) {
      setError(fail(err));
      setPhase("start");
    } finally {
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
    setPhase("start");
    setError(null);
  }

  return (
    <div className="flex min-h-full flex-col">
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-10 px-6 py-12 lg:py-16">
        {phase === "start" || phase === "working" ? (
          <div className="grid items-start gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="space-y-5">
              <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
                {t("start.kicker")}
              </p>
              <h1 className="font-heading text-4xl leading-[1.15] tracking-tight text-balance sm:text-5xl">
                {t("start.headline")}
              </h1>
              <p className="max-w-lg text-base leading-relaxed text-muted-foreground">
                {t("start.lead")}
              </p>
            </div>

            <form
              className="rounded-3xl border border-border bg-card p-6 shadow-[0_12px_40px_oklch(0.22_0.02_250_/_0.06)]"
              onSubmit={onUpload}
            >
              {error ? <ErrorBanner message={error} /> : null}

              {path === "account" ? (
                <div className="mb-6 space-y-3">
                  <AuthFields
                    email={email}
                    password={password}
                    setEmail={setEmail}
                    setPassword={setPassword}
                  />
                  <button
                    type="button"
                    className="text-sm text-muted-foreground underline-offset-4 hover:underline"
                    onClick={() => setPath("upload")}
                  >
                    {t("start.preferUpload")}
                  </button>
                </div>
              ) : (
                <p className="mb-6 text-sm text-muted-foreground">
                  {t("start.needAccount")}{" "}
                  <button
                    type="button"
                    className="font-medium text-foreground underline-offset-4 hover:underline"
                    onClick={() => setPath("account")}
                  >
                    {t("start.haveAccount")}
                  </button>
                </p>
              )}

              <div className="space-y-5">
                <Field label={t("start.period")}>
                  <TextInput
                    type="month"
                    value={period}
                    onChange={(event) => setPeriod(event.target.value)}
                    required
                    disabled={busy}
                  />
                </Field>
                <Dropzone files={files} disabled={busy} onFiles={setFiles} />
                <Button
                  type="submit"
                  size="lg"
                  className="h-11 w-full"
                  disabled={busy}
                >
                  {busy ? t("start.working") : t("start.submit")}
                </Button>
              </div>
            </form>
          </div>
        ) : null}

        {phase === "working" ? <WorkingOverlay line={workingLine} /> : null}

        {phase === "result" && intake ? (
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
            setEmail={setEmail}
            setPassword={setPassword}
            setLegalName={setLegalName}
            setTradingName={setTradingName}
            setConfirmDecline={setConfirmDecline}
            onContinue={onContinue}
            onDecline={() => void onDecline()}
            showVerboseTable={showVerboseTable}
          />
        ) : null}

        {phase === "converted" && intake ? (
          <section className="space-y-8">
            <div className="max-w-2xl space-y-3">
              <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
                {t("converted.kicker")}
              </p>
              <h1 className="font-heading text-4xl tracking-tight">
                {t("converted.headline", {
                  name: legalName.trim() || t("converted.fallbackName"),
                })}
              </h1>
              <p className="text-muted-foreground">{t("converted.lead")}</p>
            </div>
            <TeaserCards intake={intake} />
          </section>
        ) : null}

        {phase === "declined" ? (
          <section className="max-w-lg space-y-5">
            <h1 className="font-heading text-4xl tracking-tight">
              {t("declined.headline")}
            </h1>
            <p className="text-muted-foreground">{t("declined.lead")}</p>
            <Button type="button" variant="outline" size="lg" onClick={reset}>
              {t("declined.again")}
            </Button>
          </section>
        ) : null}
      </main>
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
  setEmail,
  setPassword,
  setLegalName,
  setTradingName,
  setConfirmDecline,
  onContinue,
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
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  setLegalName: (value: string) => void;
  setTradingName: (value: string) => void;
  setConfirmDecline: (value: boolean) => void;
  onContinue: (event: React.FormEvent) => void;
  onDecline: () => void;
  showVerboseTable: boolean;
}) {
  const t = useTranslations();
  return (
    <section className="space-y-10">
      <div className="max-w-2xl space-y-3">
        <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
          {t("result.kicker")}
        </p>
        <h1 className="font-heading text-4xl tracking-tight text-balance">
          {t("result.headline")}
        </h1>
        <p className="text-muted-foreground">{t("result.lead")}</p>
      </div>

      <TeaserCards intake={intake} />
      {showVerboseTable && intake.verbose_people?.length ? (
        <VerboseTable people={intake.verbose_people} />
      ) : null}

      <form
        className="max-w-lg space-y-5 rounded-3xl border border-border bg-card p-6"
        onSubmit={onContinue}
      >
        {error ? <ErrorBanner message={error} /> : null}
        <p className="font-medium">{t("result.continueTitle")}</p>
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
        {confirmDecline ? (
          <div className="space-y-3 rounded-xl bg-muted p-4 text-sm">
            <p>{t("result.declineConfirm")}</p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="destructive"
                disabled={busy}
                onClick={onDecline}
              >
                {t("result.declineYes")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => setConfirmDecline(false)}
              >
                {t("result.cancel")}
              </Button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            onClick={() => setConfirmDecline(true)}
          >
            {t("result.decline")}
          </button>
        )}
      </form>
    </section>
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
    <p className="mb-4 rounded-xl border border-destructive/20 bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {message}
    </p>
  );
}

function WorkingOverlay({ line }: { line: string }) {
  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-background/70 backdrop-blur-sm">
      <div className="flex items-center gap-3 rounded-2xl border border-border bg-card px-5 py-4 shadow-lg">
        <Loader2 className="size-5 animate-spin text-primary" />
        <p className="text-sm font-medium">{line}</p>
      </div>
    </div>
  );
}
