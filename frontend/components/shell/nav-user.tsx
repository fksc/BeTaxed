"use client";

import { ChevronsUpDown, LogOut, Settings } from "lucide-react";
import { useTranslations } from "next-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useAuthUser } from "@/hooks/use-auth-user";
import { Link, useRouter } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";
import { displayNameFromEmail, signOutUser } from "@/lib/firebase";

function initialsFromDisplayName(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function NavUser({ settingsHref }: { settingsHref: string }) {
  const t = useTranslations("userMenu");
  const { isMobile } = useSidebar();
  const { user, ready } = useAuthUser();
  const router = useRouter();

  if (!ready) {
    return null;
  }

  if (!user?.email) {
    return (
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton tooltip={t("signIn")} render={<Link href={paths.login} />}>
            <LogOut className="rotate-180" />
            <span>{t("signIn")}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    );
  }

  const name = user.displayName?.trim() || displayNameFromEmail(user.email);
  const initials = initialsFromDisplayName(name);

  async function onLogout() {
    await signOutUser();
    router.replace(paths.home);
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <SidebarMenuButton
                size="lg"
                tooltip={name}
                className="data-open:bg-sidebar-accent data-open:text-sidebar-accent-foreground"
              />
            }
          >
            <Avatar className="size-8 rounded-lg">
              <AvatarFallback className="rounded-lg">{initials}</AvatarFallback>
            </Avatar>
            <div className="grid flex-1 text-left text-sm leading-tight">
              <span className="truncate font-medium">{name}</span>
              <span className="truncate text-xs">{user.email}</span>
            </div>
            <ChevronsUpDown className="ml-auto size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuItem render={<Link href={settingsHref} />}>
              <Settings />
              {t("settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={() => void onLogout()}>
              <LogOut />
              {t("logOut")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
