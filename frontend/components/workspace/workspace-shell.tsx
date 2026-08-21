"use client";

import type { ReactNode } from "react";

import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export function WorkspaceShell({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <WorkspaceSidebar />
      <SidebarInset>{children}</SidebarInset>
    </SidebarProvider>
  );
}
