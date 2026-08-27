"use client";

import { Bell } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useNotificationsContext } from "@/hooks/use-notifications-context";
import { NotificationToasts } from "@/components/shell/notification-toasts";

function titleFor(eventType: string, t: (key: string) => string): string {
  const key = `events.${eventType}`;
  try {
    return t(key);
  } catch {
    return eventType;
  }
}

export function NotificationBell() {
  const t = useTranslations("notifications");
  const { items, unreadCount, loading, toasts, dismissToast, markAllRead, markRead } =
    useNotificationsContext();
  const unread = items.filter((item) => !item.is_read);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon"
              className="relative size-8"
              aria-label={t("title")}
            />
          }
        >
          <Bell className="size-4" />
          {unreadCount > 0 ? (
            <span className="absolute top-0.5 right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[0.625rem] font-semibold text-primary-foreground">
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          ) : null}
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-80">
          <DropdownMenuLabel className="flex items-center justify-between gap-2">
            <span>{t("unreadTitle")}</span>
            {unreadCount > 0 ? (
              <Button type="button" variant="ghost" size="xs" onClick={() => void markAllRead()}>
                {t("markAllRead")}
              </Button>
            ) : null}
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          {loading ? (
            <DropdownMenuItem disabled>{t("loading")}</DropdownMenuItem>
          ) : unread.length === 0 ? (
            <DropdownMenuItem disabled>{t("empty")}</DropdownMenuItem>
          ) : (
            unread.slice(0, 8).map((item) => (
              <DropdownMenuItem
                key={item.id}
                onClick={() => void markRead(item.id)}
              >
                {titleFor(item.event_type, t)}
              </DropdownMenuItem>
            ))
          )}
        </DropdownMenuContent>
      </DropdownMenu>
      <NotificationToasts
        toasts={toasts.map((toast) => ({
          ...toast,
          title: titleFor(toast.title, t),
        }))}
        onDismiss={dismissToast}
      />
    </>
  );
}
