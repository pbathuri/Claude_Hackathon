"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { signUp, ensureDemoDoctorSeeded } from "@/lib/auth-storage";
import { Shield } from "lucide-react";

export default function SignUpPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [licenseNumber, setLicenseNumber] = useState("");
  const [hospitalAffiliation, setHospitalAffiliation] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ensureDemoDoctorSeeded();
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const result = signUp(
      {
        fullName: fullName.trim(),
        specialty: specialty.trim(),
        licenseNumber: licenseNumber.trim(),
        hospitalAffiliation: hospitalAffiliation.trim(),
        email: email.trim(),
      },
      password
    );
    if (!result.ok) {
      setError(result.error);
      return;
    }
    router.push("/dashboard");
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#E8F4FC] to-[#F8F9FA] flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-lg space-y-8">
          <div className="text-center">
            <Link href="/" className="inline-flex items-center gap-2 text-who-blue font-heading font-bold text-lg">
              <span className="w-9 h-9 rounded-lg bg-who-blue flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </span>
              WHO Doctor Portal
            </Link>
            <h1 className="mt-6 text-2xl font-heading font-bold text-gray-900">Sign up</h1>
            <p className="mt-2 text-sm text-gray-600">Register with your professional details and license.</p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm">
            <form onSubmit={onSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Full name</label>
                <input
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Specialty</label>
                <input
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  placeholder="e.g. Internal Medicine"
                  value={specialty}
                  onChange={(e) => setSpecialty(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                  Medical license number
                </label>
                <input
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={licenseNumber}
                  onChange={(e) => setLicenseNumber(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">
                  Hospital / clinic affiliation
                </label>
                <input
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={hospitalAffiliation}
                  onChange={(e) => setHospitalAffiliation(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Email</label>
                <input
                  type="email"
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Password</label>
                <input
                  type="password"
                  className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-who-blue/25 focus:border-who-blue"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
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
                Create account
              </button>
            </form>
            <p className="mt-6 text-center text-sm text-gray-500">
              Already registered?{" "}
              <Link href="/login" className="font-semibold text-who-blue hover:underline">
                Log in
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
