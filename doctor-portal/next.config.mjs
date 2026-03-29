/** @type {import('next').NextConfig} */
const nextConfig = {
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "https://claude-hackathon-u86l.onrender.com",
  },
};
export default nextConfig;
