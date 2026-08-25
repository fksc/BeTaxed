"use client";

export function NotificationToasts({
  toasts,
  onDismiss,
}: {
  toasts: { id: string; title: string }[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) {
    return null;
  }
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex w-80 flex-col gap-2">
      {toasts.map((toast) => (
        <button
          key={toast.id}
          type="button"
          className="pointer-events-auto rounded-lg border border-border bg-card px-3 py-2 text-left text-sm shadow-md"
          onClick={() => onDismiss(toast.id)}
        >
          {toast.title}
        </button>
      ))}
    </div>
  );
}
