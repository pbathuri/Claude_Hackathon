"use client";

import { useState } from "react";
import type { Doctor } from "@/types";
import { doctorPresence, type PresenceKind } from "@/lib/doctors-online";
import { Users, ChevronUp } from "lucide-react";

function StatusDot({ kind }: { kind: PresenceKind }) {
  const cls =
    kind === "online"
      ? "bg-triage-green shadow-[0_0_0_2px_rgba(42,157,143,0.35)] animate-pulse"
      : kind === "away"
      ? "bg-triage-yellow"
      : "bg-gray-300";
  return <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${cls}`} title={kind} aria-hidden />;
}

function labelFor(kind: PresenceKind) {
  if (kind === "online") return "Online";
  if (kind === "away") return "Away";
  return "Offline";
}

interface Props {
  doctors: Doctor[];
  className?: string;
}

export default function DoctorsOnlinePanel({ doctors, className = "" }: Props) {
  return (
    <div
      className={`bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden ${className}`}
    >
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50/80">
        <h2 className="font-heading font-semibold text-gray-900 text-sm flex items-center gap-2">
          <Users className="w-4 h-4 text-who-blue" />
          Doctors online
        </h2>
        <p className="text-[11px] text-gray-500 mt-0.5">API roster, or sample colleagues when the list is empty</p>
      </div>
      <ul className="divide-y divide-gray-50 max-h-[min(420px,55vh)] overflow-y-auto scrollbar-thin">
        {doctors.map((doc) => {
          const presence = doctorPresence(doc.availability);
          return (
            <li key={doc.id} className="px-4 py-3 flex items-center gap-3 hover:bg-gray-50/80 transition-colors">
              <StatusDot kind={presence} />
              <p className="text-sm text-gray-900 min-w-0 flex-1 truncate">
                <span className="font-medium">{doc.full_name}</span>
                <span className="text-gray-400 font-normal mx-1">|</span>
                <span className="text-gray-600 font-normal">{doc.specialization}</span>
              </p>
              <span className="text-[10px] font-semibold text-gray-400 uppercase shrink-0 w-14 text-right hidden sm:inline">
                {labelFor(presence)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Mobile: floating toggle + slide-up panel */
export function DoctorsOnlineFloating({ doctors }: { doctors: Doctor[] }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="lg:hidden fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-who-blue text-white px-4 py-3 shadow-lg shadow-who-blue/30 font-semibold text-sm"
        aria-expanded={open}
        aria-controls="doctors-online-drawer"
      >
        <Users className="w-5 h-5" />
        Doctors online
        <ChevronUp className={`w-4 h-4 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/40"
          aria-hidden
          onClick={() => setOpen(false)}
        />
      )}
      <div
        id="doctors-online-drawer"
        className={`lg:hidden fixed z-40 left-4 right-4 bottom-0 max-h-[70vh] transition-transform duration-200 ease-out ${
          open ? "translate-y-0" : "translate-y-[calc(100%+1rem)] pointer-events-none"
        }`}
      >
        <div className="pb-4">
          <DoctorsOnlinePanel doctors={doctors} className="shadow-xl rounded-t-xl rounded-b-xl" />
        </div>
      </div>
    </>
  );
}
