import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Cloud Agent browsers open the dev server at 127.0.0.1. Without this,
  // Next blocks that origin and the console never leaves its initial check.
  allowedDevOrigins: ["127.0.0.1"],
  /* config options here */
  experimental: {
    // Enable experimental features if needed
  },
  // Ensure proper handling of Vercel Analytics and Speed Insights
  // headers: async () => {
  //   return [
  //     {
  //       source: '/_vercel/speed-insights/script.js',
  //       headers: [
  //         {
  //           key: 'Cache-Control',
  //           value: 'public, max-age=31536000, immutable',
  //         },
  //       ],
  //     },
  //   ];
  // },
};

export default nextConfig;
