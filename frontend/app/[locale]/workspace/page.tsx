import { WorkspaceDashboard } from "@/components/workspace/workspace-dashboard";
import { WorkspaceShell } from "@/components/workspace/workspace-shell";

export default function WorkspacePage() {
  return (
    <WorkspaceShell>
      <WorkspaceDashboard />
    </WorkspaceShell>
  );
}
