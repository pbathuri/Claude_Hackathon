"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, FileText, GitBranch, Shield, Menu, X } from "lucide-react";
import { useState } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/cases", label: "Case Queue", icon: FileText },
  { href: "/knowledge-graph", label: "Knowledge Graph", icon: GitBranch },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const nav = (
    <>
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-who-blue flex items-center justify-center">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-heading font-bold text-base tracking-tight">WHO Triage</h1>
            <p className="text-[11px] text-gray-400 tracking-wide uppercase">Doctor Portal</p>
          </div>
        </div>
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

      <div className="p-4 border-t border-white/10">
        <div className="flex items-center gap-3 px-2">
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-who-blue to-who-blue-dark flex items-center justify-center text-xs font-bold text-white">
            DR
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-200 truncate">Dr. Portal</p>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-triage-green animate-pulse" />
              <span className="text-[11px] text-gray-500">Online</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-50 md:hidden bg-sidebar text-white p-2 rounded-lg shadow-lg"
      >
        {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/50 z-30 md:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* Sidebar */}
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
