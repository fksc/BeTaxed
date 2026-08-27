"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { Field, TextInput } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { Link, useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { signInEmail } from "@/lib/firebase";

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
      router.replace(paths.companiesDashboard);
    } catch (err) {
      const code = (err as { code?: string }).code;
      if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found") {
        setError(t("errors.authInvalid"));
      } else if (code === "auth/invalid-email") {
        setError(t("errors.authEmail"));
      } else {
        setError(t("errors.generic"));
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="mx-auto flex w-full max-w-md flex-col gap-5" onSubmit={(e) => void onSubmit(e)}>
      <div className="space-y-2">
        <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">
          {t("auth.kicker")}
        </p>
        <h1 className="font-editorial text-3xl tracking-tight">{t("auth.signInTitle")}</h1>
        <p className="text-sm text-muted-foreground">{t("auth.signInLead")}</p>
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
      <Button type="submit" disabled={pending}>
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
