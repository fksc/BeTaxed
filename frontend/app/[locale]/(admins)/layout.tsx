import { AdminsShell } from "@/components/admins/admins-shell";
import { RequireAuth, RequireStaff } from "@/components/auth/require-gates";
import { NotificationsProvider } from "@/hooks/use-notifications-context";

export default function AdminsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <RequireStaff>
        <NotificationsProvider>
          <AdminsShell>{children}</AdminsShell>
        </NotificationsProvider>
      </RequireStaff>
    </RequireAuth>
  );
}
