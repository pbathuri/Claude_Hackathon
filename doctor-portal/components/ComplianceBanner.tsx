import { AlertTriangle } from "lucide-react";

export default function ComplianceBanner() {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
      <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
      <div>
        <p className="text-sm font-semibold text-amber-900">Clinical Advisory</p>
        <p className="text-sm text-amber-800 mt-0.5">
          This system provides guidance only. All medical decisions must be made by a licensed practitioner.
        </p>
      </div>
    </div>
  );
}
