"use client";

import type { ReactNode } from "react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { NotificationBell } from "@/components/shell/notification-bell";

export function ShellAppBar({ crumb }: { crumb: string }) {
  return (
    <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center gap-2 border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
      <div className="flex flex-1 items-center gap-2 px-4">
        <SidebarTrigger className="-ml-1" />
        <Separator
          orientation="vertical"
          className="mr-2 data-[orientation=vertical]:h-4"
        />
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbPage>{crumb}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
        <div className="ml-auto flex h-8 items-center gap-1">
          <NotificationBell />
          <LocaleSwitcher />
        </div>
      </div>
    </header>
  );
}

export function ShellPage({ crumb, children }: { crumb: string; children: ReactNode }) {
  return (
    <>
      <ShellAppBar crumb={crumb} />
      <div className="min-h-0 flex-1 overflow-x-hidden overflow-y-auto">
        {children}
      </div>
    </>
  );
}
