import { LoginForm } from "@/components/auth/login-form";
import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { PublicChrome } from "@/components/public/public-chrome";

export default function HomePage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-6">
      <PublicChrome />
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-8">
        <RedirectIfSignedIn>
          <LoginForm />
        </RedirectIfSignedIn>
      </div>
    </main>
  );
}
