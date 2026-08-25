"use client";

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
    <header className="flex h-16 shrink-0 items-center gap-2 border-b border-border/60 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
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
        <div className="ml-auto flex items-center gap-1">
          <NotificationBell />
          <LocaleSwitcher />
        </div>
      </div>
    </header>
  );
}
