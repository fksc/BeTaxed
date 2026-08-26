"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cancelInvite, inviteMember, resendInvite } from "@/lib/api/workspace-client";
import type { InviteOut, MemberOut } from "@/lib/api/workspace";
import { ApiError } from "@/lib/api/types";
import type { AuthOpts } from "@/lib/api/http";

const selectClass =
  "h-8 rounded-lg border border-input bg-transparent px-2 text-sm outline-none focus-visible:border-ring";

export function MembersPanel({
  members,
  invites,
  seatsUsed,
  maxMembers,
  canInvite,
  opts,
  onChanged,
}: {
  members: MemberOut[];
  invites: InviteOut[];
  seatsUsed: number;
  maxMembers: number;
  canInvite: boolean;
  opts: AuthOpts;
  onChanged: () => Promise<void>;
}) {
  const t = useTranslations("members");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("HR");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  async function onInvite() {
    setError(null);
    setBusy(true);
    try {
      const created = await inviteMember(email.trim(), role, opts);
      setEmail("");
      if (created.invite_url) {
        await navigator.clipboard.writeText(created.invite_url).catch(() => undefined);
        setCopied(created.invite_url);
      }
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("inviteFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onResend(id: string) {
    setError(null);
    setBusy(true);
    try {
      const row = await resendInvite(id, opts);
      if (row.invite_url) {
        await navigator.clipboard.writeText(row.invite_url).catch(() => undefined);
        setCopied(row.invite_url);
      }
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("resendFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function onCancel(id: string) {
    setError(null);
    setBusy(true);
    try {
      await cancelInvite(id, opts);
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("cancelFailed"));
    } finally {
      setBusy(false);
    }
  }

  const open = invites.filter((row) =>
    ["PENDING", "FAILED", "EXPIRED"].includes(row.status),
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{t("title")}</CardTitle>
        <CardDescription className="text-xs">
          {t("seats", { used: seatsUsed, max: maxMembers })}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-1">
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {copied ? (
          <p className="text-xs text-muted-foreground">{t("linkCopied")}</p>
        ) : null}
        {canInvite ? (
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs">
              {t("email")}
              <Input
                type="email"
                className="mt-1"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="text-xs">
              {t("role")}
              <select
                className={`${selectClass} mt-1 block`}
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                <option value="ADMIN">{t("roles.ADMIN")}</option>
                <option value="HR">{t("roles.HR")}</option>
                <option value="FINANCE">{t("roles.FINANCE")}</option>
              </select>
            </label>
            <Button type="button" size="sm" disabled={busy || !email.trim()} onClick={() => void onInvite()}>
              {t("invite")}
            </Button>
          </div>
        ) : null}
        <div className="space-y-2">
          <p className="text-xs font-medium">{t("membersTitle")}</p>
          {members.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("membersEmpty")}</p>
          ) : (
            members.map((row) => (
              <div key={row.id} className="text-sm">
                {row.email} · {t(`roles.${row.role}`)} ·{" "}
                {row.is_active ? t("active") : t("pendingAccept")}
              </div>
            ))
          )}
        </div>
        <div className="space-y-2">
          <p className="text-xs font-medium">{t("invitesTitle")}</p>
          {open.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("invitesEmpty")}</p>
          ) : (
            open.map((row) => (
              <div key={row.id} className="flex flex-wrap items-center gap-2 text-sm">
                <span>
                  {row.email} · {t(`roles.${row.role}`)} · {t(`status.${row.status}`)}
                </span>
                {canInvite ? (
                  <>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => void onResend(row.id)}
                    >
                      {t("resend")}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      disabled={busy}
                      onClick={() => void onCancel(row.id)}
                    >
                      {t("cancel")}
                    </Button>
                  </>
                ) : null}
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
