"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ShellPage } from "@/components/shell/shell-app-bar";
import { Field } from "@/components/intake/field";
import { createOpsCompany } from "@/lib/api/workspace-client";
import { ApiError } from "@/lib/api/types";
import { Link, useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { currentIdToken } from "@/lib/firebase";

export function OpsCompanyNewPage() {
  const t = useTranslations("admins.companyNew");
  const router = useRouter();
  const [legalName, setLegalName] = useState("");
  const [tradingName, setTradingName] = useState("");
  const [locale, setLocale] = useState("pt");
  const [nif, setNif] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminGivenName, setAdminGivenName] = useState("");
  const [adminFamilyName, setAdminFamilyName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const idToken = await currentIdToken();
    if (!idToken) {
      setError(t("needAuth"));
      return;
    }
    setPending(true);
    try {
      const created = await createOpsCompany(
        {
          legal_name: legalName.trim(),
          trading_name: tradingName.trim() || undefined,
          locale,
          nif: nif.trim() || undefined,
          admin_email: adminEmail.trim(),
          admin_given_name: adminGivenName.trim(),
          admin_family_name: adminFamilyName.trim(),
          admin_role: "ADMIN",
        },
        { idToken },
      );
      if (created.invite_url) {
        await navigator.clipboard.writeText(created.invite_url).catch(() => undefined);
      }
      router.replace(paths.adminsCompany(created.id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("failed"));
    } finally {
      setPending(false);
    }
  }

  return (
    <ShellPage crumb={t("crumb")}>
      <div className="border-b border-border bg-card px-4 py-3 sm:px-6">
        <Link href={paths.adminsCompanies} className="text-xs text-muted-foreground underline-offset-4 hover:underline">
          {t("back")}
        </Link>
        <div className="text-base font-semibold">{t("title")}</div>
        <p className="text-sm text-muted-foreground">{t("lead")}</p>
      </div>
      <form className="max-w-lg space-y-4 p-4 sm:p-6" onSubmit={(event) => void onSubmit(event)}>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Field label={t("legalName")}>
          <Input value={legalName} onChange={(event) => setLegalName(event.target.value)} required />
        </Field>
        <Field label={t("tradingName")} hint={t("optional")}>
          <Input value={tradingName} onChange={(event) => setTradingName(event.target.value)} />
        </Field>
        <Field label={t("locale")}>
          <Select
            value={locale}
            onValueChange={(value) => setLocale(value ?? "pt")}
            items={{ pt: "pt", en: "en" }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pt">pt</SelectItem>
              <SelectItem value="en">en</SelectItem>
            </SelectContent>
          </Select>
        </Field>
        <Field label={t("nif")} hint={t("optional")}>
          <Input value={nif} onChange={(event) => setNif(event.target.value)} />
        </Field>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label={t("adminGivenName")}>
            <Input
              value={adminGivenName}
              onChange={(event) => setAdminGivenName(event.target.value)}
              required
              autoComplete="given-name"
            />
          </Field>
          <Field label={t("adminFamilyName")}>
            <Input
              value={adminFamilyName}
              onChange={(event) => setAdminFamilyName(event.target.value)}
              required
              autoComplete="family-name"
            />
          </Field>
        </div>
        <Field label={t("adminEmail")}>
          <Input
            type="email"
            value={adminEmail}
            onChange={(event) => setAdminEmail(event.target.value)}
            required
            autoComplete="email"
          />
        </Field>
        <Button type="submit" disabled={pending}>
          {pending ? t("saving") : t("submit")}
        </Button>
      </form>
    </ShellPage>
  );
}
