"use client";

import { useTranslations } from "next-intl";
import {
  CreditCard,
  FileSpreadsheet,
  LayoutDashboard,
  Users,
} from "lucide-react";

import { Link, usePathname } from "@/i18n/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar";
import { LocaleSwitcher } from "@/components/locale-switcher";

export function WorkspaceSidebar() {
  const t = useTranslations("workspace");
  const pathname = usePathname();

  const items = [
    {
      href: "/workspace",
      label: t("nav.overview"),
      icon: LayoutDashboard,
      soon: false,
    },
    {
      href: "/workspace",
      label: t("nav.people"),
      icon: Users,
      soon: true,
    },
    {
      href: "/workspace",
      label: t("nav.declarations"),
      icon: FileSpreadsheet,
      soon: true,
    },
    {
      href: "/workspace",
      label: t("nav.billing"),
      icon: CreditCard,
      soon: true,
    },
  ];

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 py-4">
        <p className="font-heading truncate text-lg tracking-tight">{t("brand")}</p>
        <p className="truncate text-xs text-sidebar-foreground/70">
          {t("brandHint")}
        </p>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("navGroup")}</SidebarGroupLabel>
          <SidebarMenu>
            {items.map((item) => {
              const active = !item.soon && pathname === item.href;
              return (
                <SidebarMenuItem key={item.label}>
                  <SidebarMenuButton
                    isActive={active}
                    tooltip={item.label}
                    disabled={item.soon}
                    render={
                      item.soon ? undefined : <Link href={item.href} />
                    }
                  >
                    <item.icon />
                    <span>{item.label}</span>
                  </SidebarMenuButton>
                  {item.soon ? (
                    <SidebarMenuBadge>{t("soon")}</SidebarMenuBadge>
                  ) : null}
                </SidebarMenuItem>
              );
            })}
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="gap-3 p-3">
        <LocaleSwitcher />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
