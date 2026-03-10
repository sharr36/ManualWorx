import Link from "next/link";
import { Wrench } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-slate-950">
      {/* Left panel — branding */}
      <div className="relative hidden w-1/2 items-center justify-center overflow-hidden lg:flex">
        <div
          className="pointer-events-none absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] opacity-25"
          aria-hidden="true"
          style={{
            background: "radial-gradient(ellipse at center, rgba(16,185,129,0.4) 0%, transparent 70%)",
          }}
        />
        <div className="relative z-10 max-w-md px-12">
          <Link href="/" className="mb-8 flex items-center gap-3">
            <Wrench className="h-8 w-8 text-emerald-400" />
            <span className="text-2xl font-bold text-white tracking-tight">ManualWorx</span>
          </Link>
          <h2 className="mb-4 text-3xl font-bold leading-tight text-white">
            Expert knowledge from your service manuals
          </h2>
          <p className="text-base leading-relaxed text-slate-400">
            AI-powered manual intelligence for heavy equipment mechanics.
            Query, troubleshoot, and train — all grounded in your actual documentation.
          </p>
          <div className="mt-10 space-y-4">
            <BenefitRow text="Ask questions in plain language" />
            <BenefitRow text="Get answers with page references" />
            <BenefitRow text="Interactive schematics and diagrams" />
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex w-full items-center justify-center px-6 lg:w-1/2 lg:bg-slate-900/50">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="mb-8 text-center lg:hidden">
            <Link href="/" className="inline-flex items-center gap-2">
              <Wrench className="h-6 w-6 text-emerald-400" />
              <span className="text-xl font-bold text-white">ManualWorx</span>
            </Link>
          </div>

          {/* Card */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-xl">
            {children}
          </div>

          <p className="mt-6 text-center text-xs text-slate-600">
            By continuing, you agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    </div>
  );
}

function BenefitRow({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/10">
        <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
      </div>
      <span className="text-sm text-slate-300">{text}</span>
    </div>
  );
}
