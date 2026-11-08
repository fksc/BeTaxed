import type { MeOut } from "@/lib/api/workspace";
import { paths } from "@/lib/app-paths";

/** Staff and company members have an app home. No company means not signed in. */
export function appHomeForMe(me: MeOut): string | null {
  if (me.user_type === "BETAXED_STAFF") {
    return paths.adminsDashboard;
  }
  const active = me.memberships.filter((membership) => membership.is_active);
  if (active.length > 0) {
    return paths.companiesDashboard;
  }
  return null;
}
