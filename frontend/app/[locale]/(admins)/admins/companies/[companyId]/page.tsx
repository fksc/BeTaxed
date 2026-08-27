import { Suspense } from "react";

import { OpsCompanyDetailPage } from "@/components/admins/ops-company-detail";

export default async function Page({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  return (
    <Suspense>
      <OpsCompanyDetailPage companyId={companyId} />
    </Suspense>
  );
}
