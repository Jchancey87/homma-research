/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:5000/api/:path*',
      },
      {
        source: '/storage/:path*',
        destination: 'http://127.0.0.1:5000/storage/:path*',
      },
    ]
  },
};

export default nextConfig;
