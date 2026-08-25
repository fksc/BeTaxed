"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/api/workspace-client";
import { getApiUrl } from "@/lib/api/client";
import { currentIdToken } from "@/lib/firebase";
import type { NotificationItem } from "@/lib/api/workspace";

type Toast = { id: string; notificationId: string; title: string };

type Ctx = {
  items: NotificationItem[];
  unreadCount: number;
  toasts: Toast[];
  loading: boolean;
  refresh: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
  dismissToast: (id: string) => void;
};

const NotificationsContext = createContext<Ctx | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    const feed = await listNotifications({ idToken });
    setItems(feed.items);
    setUnreadCount(feed.unread_count);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function connect() {
      const idToken = await currentIdToken();
      if (!idToken || cancelled) {
        return;
      }
      try {
        const res = await fetch(`${getApiUrl()}/v1/notifications/stream`, {
          headers: {
            Authorization: `Bearer ${idToken}`,
            Accept: "text/event-stream",
          },
        });
        if (!res.ok || !res.body) {
          throw new Error("stream");
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (!cancelled) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";
          for (const part of parts) {
            const line = part.split("\n").find((l) => l.startsWith("data: "));
            if (!line) {
              continue;
            }
            const raw = line.slice(6);
            try {
              const payload = JSON.parse(raw) as { type?: string; event_type?: string };
              if (payload.type === "connected") {
                continue;
              }
              await refresh();
              setToasts((prev) => [
                ...prev.slice(-2),
                {
                  id: `${Date.now()}`,
                  notificationId: "",
                  title: payload.event_type ?? "notification",
                },
              ]);
            } catch {
              /* ignore */
            }
          }
        }
      } catch {
        /* reconnect */
      }
      if (!cancelled) {
        timer = window.setTimeout(() => void connect(), 2000);
      }
    }

    void connect();
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [refresh]);

  const markRead = useCallback(
    async (id: string) => {
      const idToken = await currentIdToken();
      if (!idToken) {
        return;
      }
      await markNotificationRead(id, { idToken });
      await refresh();
    },
    [refresh],
  );

  const markAllRead = useCallback(async () => {
    const idToken = await currentIdToken();
    if (!idToken) {
      return;
    }
    await markAllNotificationsRead({ idToken });
    await refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({
      items,
      unreadCount,
      toasts,
      loading,
      refresh,
      markRead,
      markAllRead,
      dismissToast: (id: string) => setToasts((prev) => prev.filter((t) => t.id !== id)),
    }),
    [items, unreadCount, toasts, loading, refresh, markRead, markAllRead],
  );

  return (
    <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
  );
}

export function useNotificationsContext(): Ctx {
  const ctx = useContext(NotificationsContext);
  if (!ctx) {
    throw new Error("NotificationsProvider missing");
  }
  return ctx;
}
