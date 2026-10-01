const isProd = process.env.NODE_ENV === 'production'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export + trailing slashes are for the production `out/` build.
  // In `next dev` they make nested routes like /forecast/ return the App Router 404.
  ...(isProd ? { output: 'export' } : {}),
  trailingSlash: isProd,
  images: {
    unoptimized: true,
  },
}

export default nextConfig
