"use client";

import { useEffect, useLayoutEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import LoadingSpinner from "@/components/LoadingSpinner";
import { ensureDemoDoctorSeeded, isLoggedIn } from "@/lib/auth-storage";

const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

export default function PortalShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  /* Run before paint so we don't stick on "Loading portal..." if effects are delayed; always flip checked */
  useIsomorphicLayoutEffect(() => {
    try {
      ensureDemoDoctorSeeded();
    } catch {
      /* localStorage blocked / quota — still allow auth check */
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    if (!checked) return;
    if (!isLoggedIn()) {
      const next = pathname || "/dashboard";
      router.replace(`/login?next=${encodeURIComponent(next)}`);
    }
  }, [checked, router, pathname]);

  if (!checked) {
    return <LoadingSpinner text="Loading portal..." />;
  }

  if (!isLoggedIn()) {
    return <LoadingSpinner text="Redirecting to sign in..." />;
  }

  return (
    <>
      <Sidebar />
      <main className="md:ml-64 min-h-screen">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pt-16 md:pt-6">{children}</div>
      </main>
    </>
  );
}
