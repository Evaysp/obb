/** @type {import('next').NextConfig} */
const BACKEND = process.env.API_URL || 'http://127.0.0.1:8000';

const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
  // Proxy /api/* to the backend so the browser never fetches cross-origin.
  // Side-effect: VPN / LAN routing quirks no longer affect client-side fetches.
  async rewrites() {
    return [
      { source: '/api/:path*', destination: `${BACKEND}/api/:path*` },
    ];
  },
};

export default nextConfig;
