/** @type {import('next').NextConfig} */
const apiUrl =
  process.env.NEXT_PUBLIC_API_URL || "https://claude-hackathon-u86l.onrender.com";

const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: apiUrl,
  },
  async redirects() {
    return [{ source: "/knowledge-graph", destination: "/tools/knowledge-graph", permanent: false }];
  },
  // Security headers apply on Render/Vercel; connect-src must allow the FastAPI origin + SSE
  async headers() {
    const connect = `'self' ${apiUrl} https://*.onrender.com http://localhost:8000 ws: wss:`;
    const csp = [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      `connect-src ${connect}`,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: csp },
        ],
      },
    ];
  },
};
export default nextConfig;
