import { PassOne } from "@/components/intake/pass-one";

function flagOn(raw: string | undefined): boolean {
  return ["TRUE", "1", "YES", "ON"].includes((raw ?? "").trim().toUpperCase());
}

export default function Home() {
  const env = (process.env.ENV || process.env.NEXT_PUBLIC_ENV || "").trim().toUpperCase();
  const verboseUi = env === "DEV" && flagOn(process.env.VERBOSE || process.env.NEXT_PUBLIC_VERBOSE);
  return <PassOne verboseUi={verboseUi} />;
}
