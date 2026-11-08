"use client";

import { useEffect, useState, type ReactNode } from "react";

import { useRouter } from "@/i18n/navigation";
import { getMe } from "@/lib/api/workspace-client";
import { currentIdToken } from "@/lib/firebase";
import { appHomeForMe } from "@/lib/session-home";
import { useAuthUser } from "@/hooks/use-auth-user";

export function RedirectIfSignedIn({ children }: { children: ReactNode }) {
  const { user, ready } = useAuthUser();
  const router = useRouter();
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!ready) {
      return;
    }
    if (!user) {
      setShow(true);
      return;
    }
    let cancelled = false;
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        if (!cancelled) setShow(true);
        return;
      }
      try {
        const me = await getMe({ idToken });
        const dest = appHomeForMe(me);
        if (dest) {
          router.replace(dest);
          return;
        }
      } catch {
        /* a session with no company is not signed in */
      }
      if (!cancelled) setShow(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, user, router]);

  if (!show) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        …
      </div>
    );
  }
  return <>{children}</>;
}
