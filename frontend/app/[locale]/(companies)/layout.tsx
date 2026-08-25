import { RequireAuth, RequireCompany } from "@/components/auth/require-gates";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";
import { NotificationsProvider } from "@/hooks/use-notifications-context";

export default function CompaniesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireAuth>
      <RequireCompany>
        <NotificationsProvider>
          <WorkspaceShell>{children}</WorkspaceShell>
        </NotificationsProvider>
      </RequireCompany>
    </RequireAuth>
  );
}
