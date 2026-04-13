/** @type {import('next').NextConfig} */
const nextConfig = {
  rewrites: async () => {
    return [
      {
        source: '/:path*',
        destination:
          process.env.NEXT_PUBLIC_API_URL
            ? `https://${process.env.NEXT_PUBLIC_API_URL}.onrender.com/api/:path*`
            : 'http://127.0.0.1:5000/api/:path*',
      },
    ]
  },
  allowedDevOrigins: [
    "http://localhost",
    "192.168.1.5"
  ],
}

module.exports = nextConfig
