import { redirect } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

type Props = { params: Promise<{ locale: string }> };

export default async function AdminsIndexPage({ params }: Props) {
  const { locale } = await params;
  redirect({ href: paths.adminsDashboard, locale });
}
