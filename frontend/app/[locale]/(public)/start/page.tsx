import { PassOne } from "@/components/intake/pass-one";
import { isVerboseUi } from "@/lib/dev-verbose";

export default function StartPage() {
  return <PassOne verboseUi={isVerboseUi()} />;
}
