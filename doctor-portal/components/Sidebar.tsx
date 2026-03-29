"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, FileText, GitBranch, Shield, Menu, X, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { getCurrentProfile, logout } from "@/lib/auth-storage";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cases", label: "Patient queue", icon: FileText },
  { href: "/tools/knowledge-graph", label: "Clinical tools", icon: GitBranch },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [displayName, setDisplayName] = useState("Doctor");
  const [specialty, setSpecialty] = useState("");
  const [hospital, setHospital] = useState("");

  useEffect(() => {
    const p = getCurrentProfile();
    if (p?.fullName) setDisplayName(p.fullName);
    setSpecialty(p?.specialty ?? "");
    setHospital(p?.hospitalAffiliation ?? "");
  }, [pathname]);

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);

  function handleLogout() {
    logout();
    router.push("/");
    setMobileOpen(false);
  }

  const nav = (
    <>
      <div className="p-6 border-b border-white/10">
        <Link href="/" className="flex items-center gap-3 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40">
          <div className="w-9 h-9 rounded-lg bg-who-blue flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-base tracking-tight">WHO Doctor Portal</h1>
            <p className="text-[11px] text-gray-400 tracking-wide uppercase">Clinical Triage</p>
          </div>
        </Link>
      </div>

      <nav className="flex-1 p-3 space-y-0.5">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileOpen(false)}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-sm font-medium ${
              isActive(item.href)
                ? "bg-who-blue text-white shadow-lg shadow-who-blue/20"
                : "text-gray-400 hover:text-white hover:bg-white/5"
            }`}
          >
            <item.icon className="w-[18px] h-[18px]" />
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="p-4 border-t border-white/10 space-y-2">
        <div className="flex items-center gap-3 px-2">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-who-blue to-who-blue-dark flex items-center justify-center text-xs font-bold text-white shrink-0">
            {displayName
              .split(" ")
              .map((n) => n[0])
              .join("")
              .slice(0, 2)
              .toUpperCase() || "DR"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">{displayName}</p>
            {specialty ? (
              <p className="text-[11px] text-gray-400 truncate mt-0.5">{specialty}</p>
            ) : null}
            {hospital ? (
              <p className="text-[10px] text-gray-500 truncate mt-0.5 leading-snug">{hospital}</p>
            ) : null}
            <div className="flex items-center gap-1.5 mt-1">
              <span className="w-2 h-2 rounded-full bg-triage-green animate-pulse" />
              <span className="text-[11px] text-gray-500">Signed in</span>
            </div>
          </div>
        </div>
        <button
          type="button"
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Log out
        </button>
      </div>
    </>
  );

  return (
    <>
      <button
        type="button"
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-50 md:hidden bg-sidebar text-white p-2 rounded-lg shadow-lg"
        aria-label={mobileOpen ? "Close menu" : "Open menu"}
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden
        />
      )}

      <aside
        className={`fixed left-0 top-0 h-screen w-64 bg-sidebar text-white flex flex-col z-40 transition-transform md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {nav}
      </aside>
    </>
  );
}
