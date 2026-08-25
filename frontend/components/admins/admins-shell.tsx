"use client";

import type { ReactNode } from "react";

import { AdminsSidebar } from "@/components/admins/admins-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export function AdminsShell({ children }: { children: ReactNode }) {
  return (
    <SidebarProvider>
      <AdminsSidebar />
      <SidebarInset>{children}</SidebarInset>
    </SidebarProvider>
  );
}
