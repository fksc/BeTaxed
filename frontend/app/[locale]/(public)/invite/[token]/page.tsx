import { AcceptInviteForm } from "@/components/auth/accept-invite-form";

export default async function Page({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6 py-12 lg:py-16">
      <AcceptInviteForm token={token} />
    </main>
  );
}
