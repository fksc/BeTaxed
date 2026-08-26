"use client";

import { Building2, CreditCard, FileInput, Flag, LayoutDashboard } from "lucide-react";
import { useTranslations } from "next-intl";

import { NavUser } from "@/components/shell/nav-user";
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
import { Link, usePathname } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function AdminsSidebar() {
  const t = useTranslations("admins");
  const pathname = usePathname();

  const items = [
    {
      href: paths.adminsDashboard,
      label: t("nav.overview"),
      icon: LayoutDashboard,
      soon: false,
    },
    {
      href: paths.adminsFlags,
      label: t("nav.flags"),
      icon: Flag,
      soon: false,
    },
    {
      href: paths.adminsCases,
      label: t("nav.cases"),
      icon: FileInput,
      soon: false,
    },
    {
      href: paths.adminsInvoices,
      label: t("nav.invoices"),
      icon: CreditCard,
      soon: false,
    },
    {
      href: paths.adminsDashboard,
      label: t("nav.companies"),
      icon: Building2,
      soon: true,
    },
    {
      href: paths.adminsDashboard,
      label: t("nav.intakes"),
      icon: FileInput,
      soon: true,
    },
  ];

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-3 py-4">
        <p className="font-heading truncate text-lg tracking-tight">{t("brand")}</p>
        <p className="truncate text-xs text-sidebar-foreground/70">{t("brandHint")}</p>
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
                    render={item.soon ? undefined : <Link href={item.href} />}
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
      <SidebarFooter className="p-2">
        <NavUser settingsHref={paths.adminsSettings} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
