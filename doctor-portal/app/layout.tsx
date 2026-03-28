import type { Metadata } from "next";
import { Inter, DM_Sans } from "next/font/google";
import Sidebar from "@/components/Sidebar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "WHO Triage — Doctor Portal",
  description: "AI-powered health triage system for medical professionals",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${dmSans.variable}`}>
      <body className="font-sans">
        <Sidebar />
        <main className="md:ml-64 min-h-screen">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pt-16 md:pt-6">
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
