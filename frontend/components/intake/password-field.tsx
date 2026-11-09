"use client";

import { useMemo, useState } from "react";
import { useTranslations } from "next-intl";

import { Field, TextInput } from "@/components/intake/field";
import {
  MIN_PASSWORD_SCORE,
  passwordBarClass,
  passwordLabelKey,
  passwordScore,
} from "@/lib/password-strength";

export function PasswordField({
  value,
  onChange,
  disabled,
  labelKey = "label",
  meter = true,
  hint,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  labelKey?: "label" | "repeat";
  meter?: boolean;
  hint?: "mismatch";
}) {
  const t = useTranslations("password");
  const score = useMemo(() => (meter ? passwordScore(value) : 0), [meter, value]);
  const [shown, setShown] = useState(false);

  return (
    <Field label={t(labelKey)}>
      <div className="relative">
        <TextInput
          type={shown ? "text" : "password"}
          autoComplete="new-password"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          required
          disabled={disabled}
          className="pr-32"
        />
        <button
          type="button"
          className="absolute top-1/2 right-2 -translate-y-1/2 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          aria-label={t("show")}
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            setShown(true);
          }}
          onPointerUp={() => setShown(false)}
          onLostPointerCapture={() => setShown(false)}
        >
          {t("show")}
        </button>
      </div>
      {hint === "mismatch" ? <p className="text-sm text-destructive">{t("mismatch")}</p> : null}
      {meter && value ? (
        <div className="mt-2 space-y-1">
          <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full ${passwordBarClass(score)}`}
              style={{ width: `${((score + 1) / 5) * 100}%` }}
            />
          </div>
          <p className="text-sm text-muted-foreground">
            {t(passwordLabelKey(score))}
            {score < MIN_PASSWORD_SCORE ? ` · ${t("needStronger")}` : ""}
          </p>
        </div>
      ) : null}
    </Field>
  );
}

export function passwordIsStrong(value: string): boolean {
  return passwordScore(value) >= MIN_PASSWORD_SCORE;
}
