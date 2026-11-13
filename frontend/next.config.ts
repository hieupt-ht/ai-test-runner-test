import type { NextConfig } from "next"

// Địa chỉ FastAPI mà server Next.js gọi tới (trong Docker là http://api:8000).
const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000"

const nextConfig: NextConfig = {
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Mọi request /api/* đi qua Next.js sang FastAPI, nên trình duyệt chỉ thấy một địa chỉ
  // (localhost:3000) và cookie đăng nhập dùng chung được.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiInternalUrl}/api/:path*` }]
  },
}

export default nextConfig
