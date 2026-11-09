"use client";

import { useEffect, useId, useRef, useState } from "react";

export const ANTEATER_CAL_LINK = "luis-anteater/anteater-sales";
export const ANTEATER_CAL_NAMESPACE = "anteater-sales";

type CalFn = ((...args: unknown[]) => void) & {
  loaded?: boolean;
  ns?: Record<string, CalFn>;
  q?: unknown[];
  config?: { forwardQueryParams?: boolean };
};

declare global {
  interface Window {
    Cal?: CalFn;
  }
}

function ensureCal(): CalFn {
  if (window.Cal) return window.Cal;

  const Cal = function (...args: unknown[]) {
    const cal = window.Cal as CalFn;
    if (!cal.loaded) {
      cal.ns = {};
      cal.q = cal.q ?? [];
      const script = document.createElement("script");
      script.src = "https://app.cal.com/embed/embed.js";
      script.async = true;
      document.head.appendChild(script);
      cal.loaded = true;
    }
    if (args[0] === "init") {
      const api = function (...inner: unknown[]) {
        api.q = api.q ?? [];
        api.q.push(inner);
      } as CalFn;
      api.q = [];
      const namespace = args[1];
      if (typeof namespace === "string") {
        cal.ns = cal.ns ?? {};
        cal.ns[namespace] = cal.ns[namespace] ?? api;
        cal.ns[namespace]!(...args);
        cal("initNamespace", namespace);
      } else {
        cal.q = cal.q ?? [];
        cal.q.push(args);
      }
      return;
    }
    cal.q = cal.q ?? [];
    cal.q.push(args);
  } as CalFn;

  Cal.ns = {};
  Cal.q = [];
  window.Cal = Cal;
  return Cal;
}

function readBookingStart(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const rec = data as Record<string, unknown>;
  const type = String(rec.type ?? rec.action ?? "");
  if (type.includes("bookingSuccessful")) {
    const bag = (
      rec.data && typeof rec.data === "object" ? rec.data : rec
    ) as Record<string, unknown>;
    const nested =
      bag.data && typeof bag.data === "object" ? (bag.data as Record<string, unknown>) : bag;
    const start = nested.startTime ?? nested.start;
    if (typeof start === "string") return start;
  }
  if (rec.detail && typeof rec.detail === "object" && rec.detail !== data) {
    return readBookingStart(rec.detail);
  }
  return null;
}

function readCalHeight(data: unknown): number | null {
  if (!data || typeof data !== "object") return null;
  const rec = data as Record<string, unknown>;
  const bags = [rec, rec.arg, rec.data, rec.detail];
  for (const bag of bags) {
    if (!bag || typeof bag !== "object") continue;
    const row = bag as Record<string, unknown>;
    for (const key of ["iframeHeight", "height"]) {
      const value = row[key];
      if (typeof value === "number" && value > 160) return value;
    }
  }
  return null;
}

export function CalInlineEmbed({
  calLink = ANTEATER_CAL_LINK,
  namespace = ANTEATER_CAL_NAMESPACE,
  onBooked,
}: {
  calLink?: string;
  namespace?: string;
  onBooked?: (startsAt: string) => void;
}) {
  const uid = useId().replace(/:/g, "");
  const elementId = `my-cal-inline-${namespace}-${uid}`;
  const [height, setHeight] = useState<number | null>(null);
  const onBookedRef = useRef(onBooked);
  useEffect(() => {
    onBookedRef.current = onBooked;
  }, [onBooked]);

  useEffect(() => {
    const Cal = ensureCal();
    Cal("init", namespace, { origin: "https://app.cal.com" });
    Cal.config = Cal.config ?? {};
    Cal.config.forwardQueryParams = true;
    const ns = Cal.ns?.[namespace] ?? Cal;
    ns("inline", {
      elementOrSelector: `#${elementId}`,
      config: { layout: "month_view", useSlotsViewOnSmallScreen: "true" },
      calLink,
    });
    ns("ui", {
      theme: "dark",
      cssVarsPerTheme: { dark: { "cal-brand": "#88375c" }, light: { "cal-brand": "#88375c" } },
      hideEventTypeDetails: false,
      layout: "month_view",
    });
    ns("on", {
      action: "*",
      callback: (event: { detail?: unknown }) => {
        const next = readCalHeight(event) ?? readCalHeight(event?.detail);
        if (next) setHeight(next);
        const start = readBookingStart(event) ?? readBookingStart(event?.detail);
        if (start) onBookedRef.current?.(start);
      },
    });
  }, [calLink, elementId, namespace]);

  useEffect(() => {
    const root = document.getElementById(elementId);
    if (!root) return;

    const applyFromIframe = () => {
      const iframe = root.querySelector("iframe");
      if (!iframe) return;
      const styled = Number.parseInt(iframe.style.height, 10);
      const next =
        Number.isFinite(styled) && styled > 160
          ? styled
          : Math.round(iframe.getBoundingClientRect().height);
      if (next > 160) setHeight((current) => (current === next ? current : next));
    };

    const observer = new MutationObserver(applyFromIframe);
    observer.observe(root, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["style", "height"],
    });
    const onMessage = (event: MessageEvent) => {
      const next = readCalHeight(event.data);
      if (next) setHeight(next);
      else requestAnimationFrame(applyFromIframe);
      const start = readBookingStart(event.data);
      if (start) onBookedRef.current?.(start);
    };
    window.addEventListener("message", onMessage);
    applyFromIframe();
    return () => {
      observer.disconnect();
      window.removeEventListener("message", onMessage);
    };
  }, [elementId]);

  return (
    <div
      id={elementId}
      className="w-full min-h-[32rem] overflow-hidden rounded-3xl border border-white/10 bg-[#0c0b0c] [&_iframe]:bg-[#0c0b0c]"
      style={{ height: height ? `${height}px` : undefined }}
    />
  );
}
