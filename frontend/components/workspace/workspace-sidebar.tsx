"use client";

import { useTranslations } from "next-intl";
import {
  CreditCard,
  FileSpreadsheet,
  LayoutDashboard,
  Users,
} from "lucide-react";

import { NavUser } from "@/components/shell/nav-user";
import { CompanySidebarBrand } from "@/components/workspace/company-sidebar-brand";
import { Link, usePathname } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
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

export function WorkspaceSidebar() {
  const t = useTranslations("workspace");
  const pathname = usePathname();

  const items = [
    {
      href: paths.companiesDashboard,
      label: t("nav.overview"),
      icon: LayoutDashboard,
      soon: false,
    },
    {
      href: paths.companiesPeople,
      label: t("nav.people"),
      icon: Users,
      soon: false,
    },
    {
      href: paths.companiesDashboard,
      label: t("nav.declarations"),
      icon: FileSpreadsheet,
      soon: true,
    },
    {
      href: paths.companiesDashboard,
      label: t("nav.billing"),
      icon: CreditCard,
      soon: true,
    },
  ];

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-2 py-3">
        <CompanySidebarBrand />
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
        <NavUser settingsHref={paths.companiesSettings} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
