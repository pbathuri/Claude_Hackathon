"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/auth-storage";
import { Shield } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const [licenseNumber, setLicenseNumber] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [nextPath, setNextPath] = useState("/dashboard");

  useEffect(() => {
    const q = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") : null;
    if (q && q.startsWith("/") && !q.startsWith("//")) setNextPath(q);
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const result = login(licenseNumber, password);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    router.push(nextPath);
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#E8F4FC] to-[#F8F9FA] flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center">
            <Link href="/" className="inline-flex items-center gap-2 text-who-blue font-heading font-bold text-lg">
              <span className="w-9 h-9 rounded-lg bg-who-blue flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </span>
              WHO Doctor Portal
            </Link>
            <h1 className="mt-6 text-2xl font-heading font-bold text-gray-900">Log in</h1>
            <p className="mt-2 text-sm text-gray-600">Use your medical license number and password.</p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <form onSubmit={onSubmit} className="space-y-5">
              <div>
                <label htmlFor="license" className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                  Medical license number
                </label>
                <input
                  id="license"
                  autoComplete="username"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  placeholder="e.g. MD-12345"
                  value={licenseNumber}
                  onChange={(e) => setLicenseNumber(e.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="password" className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              {error && (
                <p className="text-sm text-triage-red bg-red-50 border border-red-100 rounded-lg px-3 py-2" role="alert">
                  {error}
                </p>
              )}
              <button
                type="submit"
                className="w-full rounded-xl bg-who-blue py-3 text-sm font-semibold text-white hover:bg-who-blue-dark transition-colors shadow-md shadow-who-blue/20"
              >
                Log in
              </button>
            </form>
            <p className="mt-6 text-center text-sm text-gray-500">
              No account?{" "}
              <Link href="/signup" className="font-semibold text-who-blue hover:underline">
                Sign up
              </Link>
            </p>
          </div>

          <p className="text-center text-sm text-gray-500">
            <Link href="/" className="text-who-blue hover:underline">
              ← Back to home
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
