"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import HoldButton from "@/components/HoldButton";
import LetterGlitch from "@/components/LetterGlitch";
import SpecularButton from "@/components/SpecularButton";
import Stepper, { Step } from "@/components/Stepper";
import { CalInlineEmbed } from "@/components/intake/cal-inline-embed";
import { Dropzone } from "@/components/intake/dropzone";
import { Field, TextInput } from "@/components/intake/field";
import { PasswordField, passwordIsStrong } from "@/components/intake/password-field";
import { SavingsCard } from "@/components/intake/savings-card";
import { SsGuide } from "@/components/intake/ss-guide";
import { VerboseTable } from "@/components/intake/verbose-table";
import { PublicChrome } from "@/components/public/public-chrome";
import { Button } from "@/components/ui/button";
import { MonthPicker } from "@/components/ui/month-picker";
import {
  bookIntakeMeeting,
  convertIntake,
  createIntake,
  declineIntake,
  getIntake,
  uploadSsFiles,
} from "@/lib/api/intakes";
import { ApiError, type IntakeOut } from "@/lib/api/types";
import { getMe } from "@/lib/api/workspace-client";
import { isVerboseUi } from "@/lib/dev-verbose";
import { currentIdToken, ensureEmailUser, signInEmail, signOutUser } from "@/lib/firebase";
import {
  clearIntakeSession,
  loadIntakeSession,
  saveIntakeSession,
} from "@/lib/intake-session";

type Phase = "flow" | "working" | "declined";
type Finale = "talk" | "deleted" | "saved" | null;

function currentYearMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export function PassOne({ verboseUi = false }: { verboseUi?: boolean }) {
  const t = useTranslations();
  const locale = useLocale();
  const meetingTokenRef = useRef<string | null>(null);
  const sentMeetingRef = useRef<string | null>(null);
  const showVerboseTable = verboseUi || isVerboseUi();
  const workingLines = t.raw("working.lines") as string[];
  const [phase, setPhase] = useState<Phase>("flow");
  const [finale, setFinale] = useState<Finale>(null);
  const [step, setStep] = useState(1);
  const [booting, setBooting] = useState(() => loadIntakeSession() !== null);
  const [busy, setBusy] = useState(false);
  const [workingLine, setWorkingLine] = useState(workingLines[0]);
  const [error, setError] = useState<string | null>(null);
  const [intake, setIntake] = useState<IntakeOut | null>(null);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [period, setPeriod] = useState(currentYearMonth);
  const [files, setFiles] = useState<File[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");
  const [legalName, setLegalName] = useState("");
  const [tradingName, setTradingName] = useState("");
  const [signedIn, setSignedIn] = useState(false);
  const [meetingStartsAt, setMeetingStartsAt] = useState<string | null>(null);

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
        const idToken = await usableIdToken();
        setSignedIn(Boolean(idToken));
        const loaded = await getIntake(stored.intakeId, {
          sessionToken: stored.sessionToken,
          idToken,
        });
        setIntake(loaded);
        setSessionToken(stored.sessionToken);
        if (loaded.status === "CONVERTED") {
          await endBrowserSession();
          setIntake(null);
        } else if (loaded.teaser_now_monthly != null || loaded.teaser_potential_window != null) {
          setStep(3);
        }
      } catch {
        clearIntakeSession();
      } finally {
        setBooting(false);
      }
    })();
  }, []);

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

  async function endBrowserSession() {
    clearIntakeSession();
    setSessionToken(null);
    setSignedIn(false);
    await signOutUser().catch(() => undefined);
  }

  async function usableIdToken(): Promise<string | null> {
    const idToken = await currentIdToken();
    if (!idToken) {
      return null;
    }
    try {
      await getMe({ idToken });
      return idToken;
    } catch (error) {
      if (error instanceof ApiError && error.status === 403) {
        await signOutUser().catch(() => undefined);
        setSignedIn(false);
        return null;
      }
      throw error;
    }
  }

  async function authOpts() {
    return {
      sessionToken,
      idToken: await usableIdToken(),
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
      const idToken = await usableIdToken();
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
    if (!meetingStartsAt) {
      setError(t("errors.needBooking"));
      return;
    }
    if (!legalName.trim()) {
      setError(t("errors.needLegalName"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      let idToken = await usableIdToken();
      if (!idToken) {
        if (!email || !password) {
          setError(t("errors.needAuthContinue"));
          setBusy(false);
          return;
        }
        if (password !== passwordRepeat) {
          setError(t("errors.passwordMismatch"));
          setBusy(false);
          return;
        }
        if (!passwordIsStrong(password)) {
          try {
            await signInEmail(email.trim(), password);
          } catch {
            setError(t("errors.weakPassword"));
            setBusy(false);
            return;
          }
        } else {
          await ensureEmailUser(email, password);
        }
        idToken = await currentIdToken();
        setSignedIn(true);
      }
      const converted = await convertIntake(
        intake.id,
        legalName.trim(),
        tradingName.trim() || null,
        { sessionToken, idToken },
        { locale, meetingStartsAt },
      );
      setIntake(converted);
      if (converted.meeting_token) {
        meetingTokenRef.current = converted.meeting_token;
      }
      if (meetingStartsAt) {
        sentMeetingRef.current = meetingStartsAt;
      }
      setFinale("saved");
      await endBrowserSession();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        await signOutUser().catch(() => undefined);
        setSignedIn(false);
      }
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  }

  function onBooked(startsAt: string) {
    setMeetingStartsAt(startsAt);
    const token = meetingTokenRef.current;
    const current = intake;
    if (!token || !current || sentMeetingRef.current === startsAt) {
      return;
    }
    sentMeetingRef.current = startsAt;
    void bookIntakeMeeting(current.id, {
      token,
      meeting_starts_at: startsAt,
      locale,
    }).catch(() => {
      sentMeetingRef.current = null;
    });
  }

  async function onDecline() {
    if (!intake) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await declineIntake(intake.id, await authOpts());
      setIntake(null);
      setFinale("deleted");
      setStep(4);
      await endBrowserSession();
    } catch (err) {
      setError(fail(err));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    clearIntakeSession();
    setSignedIn(false);
    void signOutUser().catch(() => undefined);
    setIntake(null);
    setSessionToken(null);
    setFiles([]);
    setMeetingStartsAt(null);
    meetingTokenRef.current = null;
    sentMeetingRef.current = null;
    setPhase("flow");
    setFinale(null);
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
                  busy={busy}
                  onDecline={() => void onDecline()}
                  onTalk={() => {
                    setFinale("talk");
                    setStep(4);
                  }}
                  showVerboseTable={showVerboseTable}
                />
              ) : (
                <p className="text-muted-foreground">{t("result.waiting")}</p>
              )}
            </Step>
            <Step title={t("start.stepClose")}>
              <CloseView
                finale={finale}
                error={error}
                busy={busy}
                signedIn={signedIn}
                email={email}
                password={password}
                passwordRepeat={passwordRepeat}
                legalName={legalName}
                tradingName={tradingName}
                booked={Boolean(meetingStartsAt)}
                setEmail={setEmail}
                setPassword={setPassword}
                setPasswordRepeat={setPasswordRepeat}
                setLegalName={setLegalName}
                setTradingName={setTradingName}
                onContinue={onContinue}
                onBooked={onBooked}
              />
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
  const assurances = t.raw("assurances") as string[];
  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8">
      <div className="space-y-4">
        <p className="text-xs font-medium tracking-[0.16em] text-emerald-300 uppercase">
          {t("kicker")}
        </p>
        <h1 className="font-editorial text-4xl leading-[1.15] tracking-tight text-balance sm:text-5xl">
          {t("headline")}
        </h1>
        <p className="text-lg leading-relaxed text-muted-foreground">{t("lead")}</p>
      </div>
      <ul className="flex list-disc flex-col gap-4 pl-5 marker:text-emerald-600">
        {assurances.map((line) => (
          <li key={line} className="text-lg font-semibold leading-relaxed text-emerald-600">
            {line}
          </li>
        ))}
      </ul>
      <Button type="button" size="lg" className="h-11 w-full sm:w-fit sm:px-8" onClick={onContinue}>
        {t("continue")}
      </Button>
    </div>
  );
}

function ResultView({
  intake,
  busy,
  onDecline,
  onTalk,
  showVerboseTable,
}: {
  intake: IntakeOut;
  busy: boolean;
  onDecline: () => void;
  onTalk: () => void;
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
          <div className="space-y-3">
            <p className="font-editorial text-2xl tracking-tight">{t("result.continueAsk")}</p>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <HoldButton
                disabled={busy}
                holdTime={1600}
                backgroundColor="#3f1d28"
                fillColor="#9f1239"
                textColor="#f4f1ec"
                fillTextColor="#ffffff"
                onHold={onDecline}
              >
                {t("result.holdDelete")}
              </HoldButton>
              <SpecularButton
                disabled={busy}
                radius={14}
                lineColor="#f4f1ec"
                baseColor="#88375c"
                textColor="#f4f1ec"
                onClick={onTalk}
              >
                {t("result.talk")}
              </SpecularButton>
            </div>
          </div>
        </div>
      </div>

      {showVerboseTable && intake.verbose_people?.length ? (
        <VerboseTable people={intake.verbose_people} />
      ) : null}
    </div>
  );
}

function CloseView({
  finale,
  error,
  busy,
  signedIn,
  email,
  password,
  passwordRepeat,
  legalName,
  tradingName,
  booked,
  setEmail,
  setPassword,
  setPasswordRepeat,
  setLegalName,
  setTradingName,
  onContinue,
  onBooked,
}: {
  finale: Finale;
  error: string | null;
  busy: boolean;
  signedIn: boolean;
  email: string;
  password: string;
  passwordRepeat: string;
  legalName: string;
  tradingName: string;
  booked: boolean;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  setPasswordRepeat: (value: string) => void;
  setLegalName: (value: string) => void;
  setTradingName: (value: string) => void;
  onContinue: (event: React.FormEvent) => void;
  onBooked: (startsAt: string) => void;
}) {
  const t = useTranslations();
  if (finale === "deleted") {
    return (
      <section className="mx-auto max-w-lg space-y-5">
        <h2 className="font-editorial text-4xl tracking-tight">{t("declined.headline")}</h2>
        <p className="text-lg text-muted-foreground">{t("declined.lead")}</p>
      </section>
    );
  }
  return (
    <div className="space-y-8">
      {finale === "saved" ? (
        <div className="space-y-2">
          <h2 className="font-editorial text-3xl tracking-tight">{t("result.savedTitle")}</h2>
          <p className="text-lg text-muted-foreground">{t("result.savedLead")}</p>
        </div>
      ) : (
        <p className="text-lg text-muted-foreground">{booked ? t("result.booked") : t("result.bookFirst")}</p>
      )}
      <CalInlineEmbed onBooked={onBooked} />
      {finale === "saved" ? null : (
        <div className="rounded-3xl border border-border bg-card p-6 shadow-[0_12px_40px_oklch(0.22_0.02_250_/_0.06)]">
          {error ? <ErrorBanner message={error} /> : null}
          <form className="space-y-5" onSubmit={onContinue}>
            <div className="space-y-1">
              <p className="text-lg font-medium">{t("result.continueTitle")}</p>
              <p className="text-muted-foreground">{t("result.accountHint")}</p>
            </div>
            {!signedIn ? (
              <AuthFields
                email={email}
                password={password}
                passwordRepeat={passwordRepeat}
                setEmail={setEmail}
                setPassword={setPassword}
                setPasswordRepeat={setPasswordRepeat}
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
            <Button type="submit" size="lg" className="h-11 w-full" disabled={busy || !booked}>
              {busy ? t("result.opening") : t("result.createWorkspace")}
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}

function AuthFields({
  email,
  password,
  passwordRepeat,
  setEmail,
  setPassword,
  setPasswordRepeat,
}: {
  email: string;
  password: string;
  passwordRepeat: string;
  setEmail: (value: string) => void;
  setPassword: (value: string) => void;
  setPasswordRepeat: (value: string) => void;
}) {
  const t = useTranslations("auth");
  const mismatch = passwordRepeat.length > 0 && passwordRepeat !== password;
  return (
    <div className="grid gap-3">
      <Field label={t("email")}>
        <TextInput
          type="email"
          autoComplete="username"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </Field>
      <PasswordField value={password} onChange={setPassword} />
      <PasswordField
        value={passwordRepeat}
        onChange={setPasswordRepeat}
        labelKey="repeat"
        meter={false}
        hint={mismatch ? "mismatch" : undefined}
      />
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
