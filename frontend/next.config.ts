import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // ── Standalone output ──────────────────────────────────────────────────
  // Required for Docker production builds. Produces .next/standalone/ with
  // a self-contained server.js and minimal node_modules subset.
  output: "standalone",

  // ── Backend API proxy ─────────────────────────────────────────────────
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/:path*`,
      },
    ];
  },

  // ── Image domains ─────────────────────────────────────────────────────
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
    ],
  },

  // ── Experimental ──────────────────────────────────────────────────────
  experimental: {
    // Server Actions are stable in Next.js 14; enable here for clarity
    serverActions: {
      allowedOrigins: ["localhost:3000"],
    },
  },
};

export default nextConfig;