"use client";

import { useTranslations } from "next-intl";

import { LocaleSwitcher } from "@/components/locale-switcher";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { useAuthUser } from "@/hooks/use-auth-user";
import { Link, usePathname } from "@/i18n/navigation";
import { paths } from "@/lib/app-paths";

export function SiteHeader() {
  const t = useTranslations("marketing.nav");
  const pathname = usePathname();
  const { user, ready } = useAuthUser();
  const signedIn = ready && Boolean(user);
  const onLogin = pathname === paths.login;

  const links = [
    { href: paths.about, label: t("about") },
    { href: paths.contact, label: t("contact") },
  ];

  return (
    <header className="border-b border-border">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-6 py-5">
        <Link href={paths.home} className="font-heading text-xl tracking-tight">
          {t("brand")}
        </Link>

        <nav className="hidden items-center gap-6 text-sm sm:flex">
          {links.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              {item.label}
            </Link>
          ))}
          <LocaleSwitcher />
          {signedIn ? (
            <Button variant="outline" size="sm" render={<Link href={paths.companiesDashboard} />}>
              {t("workspace")}
            </Button>
          ) : onLogin ? null : (
            <Button variant="outline" size="sm" render={<Link href={paths.login} />}>
              {t("signIn")}
            </Button>
          )}
          <Button size="sm" render={<Link href={paths.start} />}>
            {t("start")}
          </Button>
        </nav>

        <div className="flex items-center gap-2 sm:hidden">
          <LocaleSwitcher />
          <Sheet>
            <SheetTrigger
              render={
                <Button variant="ghost" size="icon" aria-label={t("openMenu")} />
              }
            >
              <span className="flex flex-col gap-1.5">
                <span className="block h-px w-5 bg-current" />
                <span className="block h-px w-5 bg-current" />
              </span>
            </SheetTrigger>
            <SheetContent side="right">
              <SheetHeader>
                <SheetTitle>{t("brand")}</SheetTitle>
              </SheetHeader>
              <nav className="flex flex-col gap-3 px-4">
                {links.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="text-base text-foreground"
                  >
                    {item.label}
                  </Link>
                ))}
                {signedIn ? (
                  <Button variant="outline" render={<Link href={paths.companiesDashboard} />}>
                    {t("workspace")}
                  </Button>
                ) : (
                  <Button variant="outline" render={<Link href={paths.login} />}>
                    {t("signIn")}
                  </Button>
                )}
                <Button className="w-full" render={<Link href={paths.start} />}>
                  {t("start")}
                </Button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
