import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const apiBase =
      process.env.V2_API_PROXY_TARGET ||
      process.env.NEXT_PUBLIC_V2_API_BASE ||
      "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v2/:path*",
        destination: `${apiBase}/api/v2/:path*`,
      },
    ];
  },
};

export default nextConfig;
