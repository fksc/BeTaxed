import { getLocale, getTranslations } from "next-intl/server";

import { LoginForm } from "@/components/auth/login-form";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { marketingHomeUrl } from "@/lib/marketing-url";

export default async function HomePage() {
  const locale = await getLocale();
  const t = await getTranslations("auth");

  return (
    <main className="flex flex-1 flex-col px-6 py-6">
      <a
        href={marketingHomeUrl(locale)}
        className="w-fit text-sm text-foreground/80 underline-offset-4 hover:text-foreground hover:underline"
      >
        ← {t("backHome")}
      </a>
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-8">
        <RedirectIfSignedIn>
          <LoginForm />
        </RedirectIfSignedIn>
      </div>
    </main>
  );
}
