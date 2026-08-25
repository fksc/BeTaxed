import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function CompaniesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
