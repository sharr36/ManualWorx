import { Wrench } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-900">
      {/* Mountain silhouette gradient */}
      <div
        className="fixed inset-0 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900"
        aria-hidden="true"
      />
      <div
        className="fixed bottom-0 left-0 right-0 h-64"
        aria-hidden="true"
        style={{
          clipPath:
            "polygon(0 60%, 10% 45%, 20% 55%, 35% 35%, 50% 50%, 65% 30%, 80% 45%, 90% 35%, 100% 50%, 100% 100%, 0 100%)",
          background: "linear-gradient(to top, rgba(15,23,42,0.4), transparent)",
        }}
      />

      <div className="relative z-10 w-full max-w-md px-4">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mb-2 flex items-center justify-center gap-2">
            <Wrench className="h-8 w-8 text-emerald-500" />
            <span className="text-3xl font-bold text-white">ManualWorx</span>
          </div>
          <p className="text-sm text-slate-400">Leverage for the climb</p>
        </div>

        {/* Card */}
        <div className="rounded-xl bg-white p-8 shadow-2xl">{children}</div>
      </div>
    </div>
  );
}
