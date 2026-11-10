"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { AnteaterLogo } from "@/components/brand/anteater-logo";
import { Field, TextInput } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Link, useRouter } from "@/i18n/navigation";
import { getMe } from "@/lib/api/workspace-client";
import { paths } from "@/lib/app-paths";
import { currentIdToken, signInEmail } from "@/lib/firebase";
import { appHomeForMe } from "@/lib/session-home";

export function LoginForm() {
  const t = useTranslations();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await signInEmail(email.trim(), password);
      const idToken = await currentIdToken();
      if (idToken) {
        const dest = appHomeForMe(await getMe({ idToken }));
        if (dest) {
          router.replace(dest);
          return;
        }
      }
    } catch (err) {
      const code = (err as { code?: string }).code;
      if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found") {
        setError(t("errors.authInvalid"));
      } else if (code === "auth/invalid-email") {
        setError(t("errors.authEmail"));
      } else if (code === "auth/unauthorized-domain") {
        setError(t("errors.authDomain"));
      } else {
        setError(t("errors.generic"));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <form
      className="mx-auto flex w-full max-w-md flex-col gap-5 rounded-3xl border border-border bg-card p-6 shadow-[0_12px_40px_oklch(0.22_0.02_250_/_0.06)] sm:p-8"
      onSubmit={(e) => void onSubmit(e)}
    >
      <AnteaterLogo />
      <div className="space-y-2">
        <p className="text-xs font-medium tracking-[0.16em] text-accent-ink uppercase">
          {t("auth.kicker")}
        </p>
        <h1 className="font-editorial text-3xl tracking-tight">{t("auth.signInTitle")}</h1>
        <p className="text-muted-foreground">{t("auth.signInLead")}</p>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Field label={t("auth.email")}>
        <TextInput
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </Field>
      <Field label={t("auth.password")}>
        <TextInput
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </Field>
      <Button type="submit" size="lg" className="h-11" disabled={pending}>
        {pending ? t("auth.signingIn") : t("auth.signIn")}
      </Button>
      <p className="text-sm text-muted-foreground">
        {t("auth.noAccount")}{" "}
        <Link href={paths.start} className="text-foreground underline-offset-4 hover:underline">
          {t("auth.goToStart")}
        </Link>
      </p>
    </form>
  );
}
