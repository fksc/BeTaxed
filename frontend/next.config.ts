import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const allowedDevOrigins = (process.env.ALLOWED_DEV_ORIGINS ?? "")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);

const useLocalApiProxy =
  process.env.NEXT_PUBLIC_API_URL === "same-origin" ||
  process.env.NEXT_PUBLIC_API_URL === "";

const nextConfig: NextConfig = {
  output: "standalone",
  ...(allowedDevOrigins.length > 0 ? { allowedDevOrigins } : {}),
  async rewrites() {
    if (!useLocalApiProxy) {
      return [];
    }
    return [
      {
        source: "/v1/:path*",
        destination: "http://127.0.0.1:8080/v1/:path*",
      },
    ];
  },
};

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

export default withNextIntl(nextConfig);
