"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { Field, TextInput } from "@/components/intake/field";
import { Button } from "@/components/ui/button";
import { acceptInvite, getPublicInvite } from "@/lib/api/workspace-client";
import { ApiError } from "@/lib/api/types";
import { useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken, signInEmail } from "@/lib/firebase";
import { saveCompanyId } from "@/lib/company-session";
import type { PublicInviteOut } from "@/lib/api/workspace";

export function AcceptInviteForm({ token }: { token: string }) {
  const t = useTranslations("invite");
  const router = useRouter();
  const [invite, setInvite] = useState<PublicInviteOut | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        setInvite(await getPublicInvite(token));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : t("missing"));
      }
    })();
  }, [token, t]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!invite) {
      return;
    }
    setError(null);
    if (invite.needs_password) {
      if (password.length < 8) {
        setError(t("passwordShort"));
        return;
      }
      if (password !== confirm) {
        setError(t("passwordMismatch"));
        return;
      }
    }
    setPending(true);
    try {
      if (invite.needs_password) {
        const accepted = await acceptInvite(token, { password });
        await signInEmail(invite.email, password);
        saveCompanyId(accepted.company_id);
      } else {
        await signInEmail(invite.email, password);
        const idToken = await currentIdToken();
        const accepted = await acceptInvite(token, {}, { idToken });
        saveCompanyId(accepted.company_id);
      }
      router.replace(paths.companiesDashboard);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("failed"));
    } finally {
      setPending(false);
    }
  }

  const blocked =
    invite &&
    (invite.status === "EXPIRED" ||
      invite.status === "CANCELLED" ||
      invite.status === "FAILED");

  return (
    <form className="mx-auto flex w-full max-w-md flex-col gap-5" onSubmit={(event) => void onSubmit(event)}>
      <div className="space-y-2">
        <p className="text-xs font-medium tracking-[0.16em] text-accent uppercase">{t("kicker")}</p>
        <h1 className="font-heading text-3xl tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">
          {invite ? t("lead", { company: invite.company_name, role: invite.role }) : t("loading")}
        </p>
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {blocked ? (
        <p className="text-sm text-muted-foreground">{t("askResend")}</p>
      ) : invite?.needs_password ? (
        <>
          <Field label={t("password")}>
            <TextInput
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>
          <Field label={t("confirm")}>
            <TextInput
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              required
            />
          </Field>
          <Button type="submit" disabled={pending || !invite}>
            {pending ? t("working") : t("setPassword")}
          </Button>
        </>
      ) : invite ? (
        <>
          <p className="text-sm text-muted-foreground">{t("existing")}</p>
          <Field label={t("password")}>
            <TextInput
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </Field>
          <Button type="submit" disabled={pending}>
            {pending ? t("working") : t("accept")}
          </Button>
        </>
      ) : null}
    </form>
  );
}
