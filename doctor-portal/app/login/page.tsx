"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

/**
 * Lightweight portal gate: stores doctor profile id for X-Doctor-ID.
 * Pair with DEMO_MODE=0 and real auth in a future iteration.
 */
export default function LoginPage() {
  const router = useRouter();
  const [doctorId, setDoctorId] = useState("");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const v = doctorId.trim();
    if (v) {
      localStorage.setItem("whoPortalDoctorId", v);
    } else {
      localStorage.removeItem("whoPortalDoctorId");
    }
    router.push("/");
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="w-full max-w-md space-y-6 rounded-xl border border-gray-200 bg-white p-8 shadow-sm">
        <div>
          <h1 className="text-xl font-heading font-bold text-gray-900">Doctor portal</h1>
          <p className="mt-1 text-sm text-gray-500">
            Enter your backend <code className="text-xs bg-gray-100 px-1 rounded">doctor_profiles.id</code>{" "}
            UUID to send <code className="text-xs bg-gray-100 px-1 rounded">X-Doctor-ID</code> on API calls.
            Leave blank for demo mode.
          </p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Doctor ID (optional)</label>
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              placeholder="e.g. uuid from /doctors/"
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-who-blue py-2 text-sm font-semibold text-white hover:bg-who-blue-dark"
          >
            Continue
          </button>
        </form>
        <p className="text-center text-sm text-gray-500">
          <Link href="/" className="text-who-blue hover:underline">
            Skip to dashboard
          </Link>
        </p>
      </div>
    </div>
  );
}
