"use client";

import type { ReactNode } from "react";

import { AdminsSidebar } from "@/components/admins/admins-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export function AdminsShell({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider className="h-svh min-h-0 overflow-hidden">
      <AdminsSidebar />
      <SidebarInset className="min-h-0 overflow-hidden">{children}</SidebarInset>
    </SidebarProvider>
  );
}
