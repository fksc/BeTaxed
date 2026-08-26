"use client";

import { useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { getMe, getMeCompany } from "@/lib/api/workspace-client";
import { loadCompanyId, saveCompanyId, saveWorkspaceName } from "@/lib/company-session";
import { currentIdToken } from "@/lib/firebase";
import { useAuthUser } from "@/hooks/use-auth-user";
import { useEffect, useState, type ReactNode } from "react";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuthUser();
  const router = useRouter();

  useEffect(() => {
    if (ready && !user) {
      router.replace(paths.login);
    }
  }, [ready, user, router]);

  if (!ready || !user) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        …
      </div>
    );
  }
  return <>{children}</>;
}

export function RequireCompany({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ok, setOk] = useState(false);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        router.replace(paths.login);
        return;
      }
      try {
        const me = await getMe({ idToken });
        if (me.user_type === "BETAXED_STAFF") {
          router.replace(paths.adminsDashboard);
          return;
        }
        const active = me.memberships.filter((m) => m.is_active);
        if (active.length === 0) {
          router.replace(paths.start);
          return;
        }
        const stored = loadCompanyId();
        const match = stored && active.some((m) => m.company_id === stored);
        const companyId = match ? stored : active[0].company_id;
        saveCompanyId(companyId);
        try {
          const scope = await getMeCompany({ idToken, companyId });
          saveWorkspaceName(scope.legal_name);
        } catch {
          /* name is filled on the dashboard if this call fails */
        }
        setOk(true);
      } catch {
        router.replace(paths.login);
      }
    })();
  }, [router]);

  if (!ok) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        …
      </div>
    );
  }
  return <>{children}</>;
}

export function RequireStaff({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [ok, setOk] = useState(false);

  useEffect(() => {
    void (async () => {
      const idToken = await currentIdToken();
      if (!idToken) {
        router.replace(paths.login);
        return;
      }
      try {
        const me = await getMe({ idToken });
        if (me.user_type !== "BETAXED_STAFF") {
          router.replace(paths.home);
          return;
        }
        setOk(true);
      } catch {
        router.replace(paths.login);
      }
    })();
  }, [router]);

  if (!ok) {
    return (
      <div className="flex min-h-svh items-center justify-center text-sm text-muted-foreground">
        …
      </div>
    );
  }
  return <>{children}</>;
}
