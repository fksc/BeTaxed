import { Suspense } from "react";

import { OpsEmployeeDetailPage } from "@/components/admins/ops-employee-detail";

export default async function Page({
  params,
}: {
  params: Promise<{ companyId: string; employeeId: string }>;
}) {
  const { companyId, employeeId } = await params;
  return (
    <Suspense>
      <OpsEmployeeDetailPage companyId={companyId} employeeId={employeeId} />
    </Suspense>
  );
}
