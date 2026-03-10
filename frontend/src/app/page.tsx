import Link from "next/link";
import {
  BookOpen,
  ChevronRight,
  GraduationCap,
  Image,
  MessageSquare,
  Search,
  Shield,
  Upload,
  Wrench,
  Zap,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Nav */}
      <nav className="fixed top-0 z-50 w-full border-b border-white/5 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2.5">
            <Wrench className="h-6 w-6 text-emerald-400" />
            <span className="text-lg font-bold tracking-tight">ManualWorx</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 transition hover:text-white"
            >
              Sign In
            </Link>
            <Link
              href="/signup"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-500"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden pt-32 pb-20">
        {/* Glow effect */}
        <div
          className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] opacity-20"
          aria-hidden="true"
          style={{
            background: "radial-gradient(ellipse at center, rgba(16,185,129,0.3) 0%, transparent 70%)",
          }}
        />

        <div className="relative mx-auto max-w-4xl px-6 text-center">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-4 py-1.5 text-sm text-emerald-400">
            <Zap className="h-3.5 w-3.5" />
            AI-Powered Manual Intelligence
          </div>

          <h1 className="mb-6 text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
            Turn equipment manuals into{" "}
            <span className="bg-gradient-to-r from-emerald-400 to-emerald-300 bg-clip-text text-transparent">
              expert knowledge
            </span>
          </h1>

          <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-slate-400">
            Query service manuals in plain language, troubleshoot with interactive
            schematics, and train your team — all grounded in your actual documentation.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="group inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-7 py-3.5 text-base font-semibold text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-500 hover:shadow-emerald-500/30"
            >
              Start Free Trial
              <ChevronRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#features"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-7 py-3.5 text-base font-semibold text-slate-300 transition hover:border-slate-500 hover:text-white"
            >
              See How It Works
            </a>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-white/5 bg-slate-900/50 py-20">
        <div className="mx-auto max-w-5xl px-6">
          <h2 className="mb-12 text-center text-sm font-semibold uppercase tracking-wider text-slate-500">
            How it works
          </h2>
          <div className="grid gap-8 sm:grid-cols-3">
            <StepCard
              step="1"
              icon={<Upload className="h-5 w-5" />}
              title="Upload Manuals"
              description="Drop in PDFs of your service manuals. We OCR, chunk, and index every page."
            />
            <StepCard
              step="2"
              icon={<Search className="h-5 w-5" />}
              title="Ask Questions"
              description="Query in plain language. Get answers with page references and confidence scores."
            />
            <StepCard
              step="3"
              icon={<Shield className="h-5 w-5" />}
              title="Work Confidently"
              description="Every answer is grounded in your manuals — with source citations you can verify."
            />
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="py-24">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-4 text-center">
            <h2 className="mb-3 text-3xl font-bold tracking-tight">
              Everything your shop needs
            </h2>
            <p className="mx-auto max-w-lg text-slate-400">
              Built for heavy equipment mechanics who need fast, accurate answers from their service manuals.
            </p>
          </div>

          <div className="mt-14 grid gap-5 sm:grid-cols-2">
            <FeatureCard
              icon={<MessageSquare className="h-5 w-5" />}
              title="Query Manuals"
              description="Ask questions in plain language. Get answers with page references, confidence scores, and spec values — backed by your actual service manuals."
            />
            <FeatureCard
              icon={<BookOpen className="h-5 w-5" />}
              title="Troubleshoot"
              description="Describe the problem, get step-by-step diagnostic procedures with safety warnings and torque specs. AI-powered but manual-grounded."
            />
            <FeatureCard
              icon={<Image className="h-5 w-5" />}
              title="Interactive Schematics"
              description="Hydraulic and electrical diagrams come alive. Click components, trace flows, switch operating states. AI-annotated with part locations."
            />
            <FeatureCard
              icon={<GraduationCap className="h-5 w-5" />}
              title="Train Your Team"
              description="Teach-then-troubleshoot mode builds understanding before fixing. Auto-generated learning paths, quizzes, and progress tracking."
            />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="border-t border-white/5 bg-slate-900/50 py-20">
        <div className="mx-auto max-w-2xl px-6 text-center">
          <h2 className="mb-4 text-2xl font-bold tracking-tight sm:text-3xl">
            Ready to put your manuals to work?
          </h2>
          <p className="mb-8 text-slate-400">
            Join shops and technicians already using ManualWorx to work faster and smarter.
          </p>
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-500"
          >
            Get Started Free
            <ChevronRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-sm text-slate-600">
        ManualWorx by Fulcrum Systems
      </footer>
    </div>
  );
}

function StepCard({
  step,
  icon,
  title,
  description,
}: {
  step: string;
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-600/10 text-emerald-400">
        {icon}
      </div>
      <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Step {step}
      </div>
      <h3 className="mb-2 text-lg font-semibold">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-400">{description}</p>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="group rounded-xl border border-slate-800 bg-slate-900/50 p-6 transition hover:border-emerald-500/30 hover:bg-slate-900">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 transition group-hover:bg-emerald-500/15">
        {icon}
      </div>
      <h3 className="mb-2 text-base font-semibold">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-400">{description}</p>
    </div>
  );
}
