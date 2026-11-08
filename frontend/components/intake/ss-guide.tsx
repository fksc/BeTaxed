"use client";

import { CircleHelp, X } from "lucide-react";
import { useTranslations } from "next-intl";
import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";

const PORTAL_URL = "https://app.seg-social.pt/ptss";

const SHARED_IMAGES = [
  "/guide/sign-in.png",
  "/guide/search.png",
  "/guide/search-form.png",
  "/guide/search-form.png",
  "/guide/search-form.png",
  "/guide/search-form.png",
];
const SCENARIO_A_IMAGES = ["/guide/obter-zip.png"];
const SCENARIO_B_IMAGES = [
  "/guide/obter-messages.png",
  "/guide/messages.png",
  "/guide/attachments.png",
];

type GuideStep = {
  title: string;
  body: string;
};

type Place =
  | { kind: "shared"; index: number }
  | { kind: "fork" }
  | { kind: "scenario"; which: "a" | "b"; index: number };

const STEP_TWO_IMAGE = SHARED_IMAGES[1];

export function SsGuide() {
  const t = useTranslations("guide");
  const buttonRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [peekAt, setPeekAt] = useState<{ top: number; left: number } | null>(null);
  const [place, setPlace] = useState<Place>({ kind: "shared", index: 0 });
  const shared = t.raw("shared") as GuideStep[];
  const scenarioA = t.raw("scenarioA") as GuideStep[];
  const scenarioB = t.raw("scenarioB") as GuideStep[];

  useEffect(() => {
    if (!open) {
      return;
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function openGuide() {
    setPeekAt(null);
    setPlace({ kind: "shared", index: 0 });
    setOpen(true);
  }

  function showPeek() {
    setPeekAt(peekStyle(buttonRef.current));
  }

  function back() {
    setPlace((current) => {
      if (current.kind === "scenario") {
        if (current.index === 0) {
          return { kind: "fork" };
        }
        return { ...current, index: current.index - 1 };
      }
      if (current.kind === "fork") {
        return { kind: "shared", index: shared.length - 1 };
      }
      return { kind: "shared", index: Math.max(0, current.index - 1) };
    });
  }

  function forward() {
    setPlace((current) => {
      if (current.kind === "shared") {
        if (current.index < shared.length - 1) {
          return { kind: "shared", index: current.index + 1 };
        }
        return { kind: "fork" };
      }
      if (current.kind === "scenario") {
        const total = current.which === "b" ? scenarioB.length : scenarioA.length;
        if (current.index < total - 1) {
          return { ...current, index: current.index + 1 };
        }
      }
      return current;
    });
  }

  const scenarioSteps = place.kind === "scenario" && place.which === "b" ? scenarioB : scenarioA;
  const step =
    place.kind === "shared"
      ? shared[place.index]
      : place.kind === "scenario"
        ? scenarioSteps[place.index]
        : null;
  const atScenarioEnd =
    place.kind === "scenario" && place.index >= scenarioSteps.length - 1;
  const atSharedStart = place.kind === "shared" && place.index === 0;
  const image =
    place.kind === "shared"
      ? SHARED_IMAGES[place.index]
      : place.kind === "scenario"
        ? (place.which === "b" ? SCENARIO_B_IMAGES : SCENARIO_A_IMAGES)[place.index]
        : "/guide/search-form.png";

  const dialog = open ? (
        <div className="fixed inset-0 z-[80] grid place-items-center p-4 sm:p-8">
          <button
            type="button"
            aria-label={t("close")}
            className="absolute inset-0 bg-black/60"
            onClick={() => setOpen(false)}
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="ss-guide-title"
            className="relative flex max-h-[calc(100vh-4rem)] w-full max-w-6xl flex-col overflow-hidden rounded-3xl border border-border bg-card shadow-lg"
          >
            <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
              <div className="space-y-1">
                <p className="text-xs font-medium tracking-[0.16em] text-accent-ink uppercase">
                  {t("kicker")}
                </p>
                <h2 id="ss-guide-title" className="font-editorial text-2xl tracking-tight">
                  {t("title")}
                </h2>
              </div>
              <button
                type="button"
                aria-label={t("close")}
                onClick={() => setOpen(false)}
                className="grid size-9 place-items-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="grid min-h-0 flex-1 gap-6 overflow-y-auto px-6 py-6 lg:grid-cols-[minmax(0,22rem)_1fr] lg:overflow-hidden">
              <div className="lg:overflow-y-auto">
              {place.kind === "fork" ? (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">{t("forkProgress")}</p>
                  <p className="text-lg leading-relaxed">{t("forkLead")}</p>
                  <div className="grid gap-3">
                    <Button
                      type="button"
                      size="lg"
                      className="h-11"
                      onClick={() => setPlace({ kind: "scenario", which: "a", index: 0 })}
                    >
                      {t("under50")}
                    </Button>
                    <Button
                      type="button"
                      size="lg"
                      variant="outline"
                      className="h-11"
                      onClick={() => setPlace({ kind: "scenario", which: "b", index: 0 })}
                    >
                      {t("over50")}
                    </Button>
                  </div>
                </div>
              ) : step ? (
                <div className="space-y-3">
                  <p className="text-sm text-muted-foreground">
                    {place.kind === "shared"
                      ? t("progress", { current: place.index + 1, total: shared.length })
                      : t("scenarioProgress", {
                          scenario: place.which === "a" ? t("scenarioAName") : t("scenarioBName"),
                          current: place.index + 1,
                          total: scenarioSteps.length,
                        })}
                  </p>
                  <p className="font-editorial text-3xl tracking-tight">{step.title}</p>
                  <p className="text-lg leading-relaxed text-muted-foreground">{step.body}</p>
                  {place.kind === "shared" && place.index === 0 ? (
                    <a
                      href={PORTAL_URL}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-block font-medium text-foreground underline-offset-4 hover:underline"
                    >
                      {t("portal")}
                    </a>
                  ) : null}
                </div>
              ) : null}
              </div>
              <div className="relative min-h-80 overflow-hidden rounded-3xl border border-border bg-white lg:min-h-[32rem]">
                <Image
                  src={image}
                  alt={step?.title ?? t("forkProgress")}
                  fill
                  sizes="(min-width: 1024px) 60vw, 100vw"
                  className="object-contain"
                />
              </div>
            </div>
            <div className="flex items-center justify-between gap-3 border-t border-border px-6 py-4">
              <Button type="button" variant="outline" disabled={atSharedStart} onClick={back}>
                {t("back")}
              </Button>
              {place.kind === "fork" ? null : atScenarioEnd ? (
                <Button type="button" onClick={() => setOpen(false)}>
                  {t("done")}
                </Button>
              ) : (
                <Button type="button" onClick={forward}>
                  {t("next")}
                </Button>
              )}
            </div>
          </div>
        </div>
  ) : null;

  const peekCard =
    peekAt && !open && typeof document !== "undefined"
      ? createPortal(
          <div
            className="pointer-events-none fixed z-[70] w-72 rounded-3xl border border-border bg-card p-3 shadow-lg"
            style={{ top: peekAt.top, left: peekAt.left }}
          >
            <p className="font-editorial text-xl tracking-tight">{t("peek")}</p>
            <div className="relative mt-3 h-36 overflow-hidden rounded-2xl border border-border bg-white">
              <Image
                src={STEP_TWO_IMAGE}
                alt=""
                fill
                sizes="288px"
                className="object-cover object-left-top"
              />
            </div>
          </div>,
          document.body,
        )
      : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-label={t("open")}
        onClick={openGuide}
        onMouseEnter={showPeek}
        onMouseLeave={() => setPeekAt(null)}
        onFocus={showPeek}
        onBlur={() => setPeekAt(null)}
        className={`relative grid size-11 shrink-0 place-items-center rounded-full border border-[#88375c] bg-[#88375c]/15 text-[#e4b4c4] transition-colors hover:bg-[#88375c]/30 ${open ? "" : "guide-pulse"}`}
      >
        <CircleHelp className="size-5" />
      </button>
      {peekCard}
      {dialog && typeof document !== "undefined" ? createPortal(dialog, document.body) : null}
    </>
  );
}

function peekStyle(button: HTMLButtonElement | null): { top: number; left: number } {
  if (!button || typeof window === "undefined") {
    return { top: 0, left: 0 };
  }
  const rect = button.getBoundingClientRect();
  const width = 288;
  const left = Math.min(Math.max(16, rect.right - width), window.innerWidth - width - 16);
  const below = rect.bottom + 12;
  const top = below + 220 > window.innerHeight ? Math.max(16, rect.top - 232) : below;
  return { top, left };
}
