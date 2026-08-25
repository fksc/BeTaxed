import { apiJson, type AuthOpts } from "@/lib/api/http";
import type { MeOut, MismatchFlag, NotificationList, PersonOut } from "@/lib/api/workspace";

export async function getMe(opts: AuthOpts): Promise<MeOut> {
  return apiJson<MeOut>("/v1/me", { method: "GET" }, opts);
}

export async function listPeople(opts: AuthOpts): Promise<PersonOut[]> {
  return apiJson<PersonOut[]>("/v1/people", { method: "GET" }, opts);
}

export async function uploadPersonContract(
  employeeId: string,
  file: File,
  opts: AuthOpts,
): Promise<{ id: string; review_status: string }> {
  const body = new FormData();
  body.set("file", file);
  return apiJson(`/v1/people/${employeeId}/contracts`, { method: "POST", body }, opts);
}

export async function listNotifications(opts: AuthOpts): Promise<NotificationList> {
  return apiJson<NotificationList>("/v1/notifications", { method: "GET" }, opts);
}

export async function markNotificationRead(
  notificationId: string,
  opts: AuthOpts,
): Promise<void> {
  await apiJson(`/v1/notifications/${notificationId}/read`, { method: "POST" }, opts);
}

export async function markAllNotificationsRead(opts: AuthOpts): Promise<void> {
  await apiJson("/v1/notifications/read-all", { method: "POST" }, opts);
}

export async function listContractFlags(opts: AuthOpts): Promise<MismatchFlag[]> {
  return apiJson<MismatchFlag[]>("/v1/ops/contract-flags", { method: "GET" }, opts);
}

export async function applyContractDocument(
  documentId: string,
  opts: AuthOpts,
): Promise<void> {
  await apiJson(
    `/v1/ops/employment-documents/${documentId}/apply`,
    { method: "POST" },
    opts,
  );
}
