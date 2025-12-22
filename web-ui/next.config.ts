import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Improve stability and performance
  reactStrictMode: true,

  // Prevent memory leaks during development
  onDemandEntries: {
    // Period (in ms) where the server will keep pages in the buffer
    maxInactiveAge: 60 * 1000,
    // Number of pages that should be kept simultaneously without being disposed
    pagesBufferLength: 5,
  },

  // Optimize for development
  compiler: {
    removeConsole: false,
  },

  // Handle external packages that might cause issues
  transpilePackages: [],
};

export default nextConfig;
