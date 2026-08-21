export function isVerboseUi(): boolean {
  const env = (process.env.NEXT_PUBLIC_ENV ?? "").trim().toUpperCase();
  const verbose = (process.env.NEXT_PUBLIC_VERBOSE ?? "").trim().toUpperCase();
  return env === "DEV" && ["TRUE", "1", "YES", "ON"].includes(verbose);
}
