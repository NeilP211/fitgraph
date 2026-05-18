import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow the Next.js Image component to load images from the API server.
  // In development this is localhost:8000; in production set NEXT_PUBLIC_API_URL
  // and add the hostname here or use `unoptimized` on the Image component.
  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/images/**",
      },
    ],
  },
};

export default nextConfig;
