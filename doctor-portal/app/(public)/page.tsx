import Link from "next/link";
import { Shield, Stethoscope, FileCheck, Radio, Lock } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-[#E8F4FC] via-[#F8F9FA] to-white">
      <header className="border-b border-who-blue/10 bg-white/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-who-blue flex items-center justify-center shadow-md shadow-who-blue/20">
              <Shield className="w-5 h-5 text-white" aria-hidden />
            </div>
            <div>
              <p className="font-heading font-bold text-gray-900 text-sm sm:text-base">WHO Doctor Portal</p>
              <p className="text-[10px] sm:text-[11px] text-who-blue font-semibold uppercase tracking-wider">
                Clinical Triage Network
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link
              href="/login"
              className="text-sm font-semibold text-who-blue hover:text-who-blue-dark px-3 py-2 rounded-lg hover:bg-who-blue/5 transition-colors"
            >
              Log In
            </Link>
            <Link
              href="/signup"
              className="text-sm font-semibold text-white bg-who-blue hover:bg-who-blue-dark px-4 py-2 rounded-lg shadow-sm transition-colors"
            >
              Sign Up
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-12 sm:pt-20 pb-16">
          <div className="max-w-3xl">
            <p className="text-who-blue font-semibold text-sm uppercase tracking-wide mb-3">
              Licensed clinicians only
            </p>
            <h1 className="font-heading text-4xl sm:text-5xl font-bold text-gray-900 leading-tight">
              A trusted workspace for reviewing triage cases and submitting medical reports
            </h1>
            <p className="mt-5 text-lg text-gray-600 leading-relaxed">
              Access patient queues, document clinical findings with structured reports, and coordinate follow-up
              through secure communication preferences—in line with professional public health practice.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href="/signup"
                className="inline-flex items-center justify-center rounded-xl bg-who-blue text-white font-semibold px-6 py-3.5 shadow-lg shadow-who-blue/25 hover:bg-who-blue-dark transition-colors"
              >
                Create account
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-xl border-2 border-who-blue text-who-blue font-semibold px-6 py-3.5 hover:bg-who-blue/5 transition-colors"
              >
                Log in with license
              </Link>
            </div>
          </div>

          <div className="mt-16 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                icon: Stethoscope,
                title: "Case queue",
                desc: "Prioritized patient presentations with triage context and safety flags.",
              },
              {
                icon: FileCheck,
                title: "Structured reports",
                desc: "Vitals, medications, allergies, and clinical notes in one submission flow.",
              },
              {
                icon: Radio,
                title: "Follow-up channels",
                desc: "Choose how results reach patients: voice, SMS, or phone call.",
              },
              {
                icon: Lock,
                title: "License-based access",
                desc: "Sign in with your medical license number and a secure password.",
              },
            ].map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="bg-white rounded-2xl border border-gray-100 p-6 shadow-sm hover:shadow-md hover:border-who-blue/15 transition-all"
              >
                <div className="w-11 h-11 rounded-xl bg-[#E8F4FC] flex items-center justify-center mb-4">
                  <Icon className="w-5 h-5 text-who-blue" aria-hidden />
                </div>
                <h2 className="font-heading font-semibold text-gray-900">{title}</h2>
                <p className="text-sm text-gray-600 mt-2 leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="bg-who-blue text-white py-12 sm:py-16">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div>
              <h2 className="font-heading text-2xl font-bold">Ready to enter the portal?</h2>
              <p className="text-white/85 mt-2 text-sm sm:text-base max-w-xl">
                Use your medical license credentials. New clinicians can register in minutes.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 shrink-0">
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-xl bg-white text-who-blue font-semibold px-6 py-3 hover:bg-gray-50 transition-colors"
              >
                Log In
              </Link>
              <Link
                href="/signup"
                className="inline-flex items-center justify-center rounded-xl border-2 border-white/80 text-white font-semibold px-6 py-3 hover:bg-white/10 transition-colors"
              >
                Sign Up
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-gray-200 py-8 text-center text-xs text-gray-500">
        WHO-inspired clinical portal UI for demonstration. Not affiliated with the World Health Organization.
      </footer>
    </div>
  );
}
