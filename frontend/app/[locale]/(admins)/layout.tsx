import { AdminsShell } from "@/components/admins/admins-shell";

export default function AdminsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminsShell>{children}</AdminsShell>;
}
