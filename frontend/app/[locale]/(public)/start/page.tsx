import { RedirectIfSignedIn } from "@/components/auth/redirect-if-signed-in";
import { PassOne } from "@/components/intake/pass-one";
import { isVerboseUi } from "@/lib/dev-verbose";

export default function StartPage() {
  return (
    <RedirectIfSignedIn>
      <PassOne verboseUi={isVerboseUi()} />
    </RedirectIfSignedIn>
  );
}
