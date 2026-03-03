import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Note: output: "export" is incompatible with API routes
  // API routes require server mode to function
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
