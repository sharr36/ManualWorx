import Link from "next/link";
import {
  BookOpen,
  GraduationCap,
  Image,
  MessageSquare,
  Wrench,
} from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-900">
      {/* Hero */}
      <div className="relative overflow-hidden">
        {/* Mountain gradient background */}
        <div
          className="absolute inset-0 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900"
          aria-hidden="true"
        />
        <div
          className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-slate-900/80 to-transparent"
          aria-hidden="true"
          style={{
            clipPath: "polygon(0 60%, 15% 40%, 30% 55%, 50% 30%, 70% 50%, 85% 35%, 100% 55%, 100% 100%, 0 100%)",
            background: "linear-gradient(to top, rgba(15,23,42,0.6), transparent)",
          }}
        />

        <div className="relative mx-auto max-w-5xl px-6 py-32 text-center">
          <div className="mb-6 flex items-center justify-center gap-3">
            <Wrench className="h-10 w-10 text-emerald-500" />
            <h1 className="text-4xl font-bold text-white sm:text-5xl">
              ManualWorx
            </h1>
          </div>
          <p className="mb-3 text-xl text-slate-300 sm:text-2xl">
            Turn equipment manuals into expert knowledge
          </p>
          <p className="mx-auto mb-10 max-w-2xl text-base text-slate-400">
            AI-powered manual intelligence for heavy equipment mechanics.
            Query service manuals in natural language, troubleshoot with
            interactive schematics, and train your team — all in one platform.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className="rounded-lg bg-emerald-600 px-8 py-3 text-lg font-semibold text-white transition hover:bg-emerald-500"
            >
              Get Started
            </Link>
            <a
              href="#features"
              className="rounded-lg border border-slate-600 px-8 py-3 text-lg font-semibold text-slate-300 transition hover:border-slate-400 hover:text-white"
            >
              Learn More
            </a>
          </div>
        </div>
      </div>

      {/* Features */}
      <div id="features" className="mx-auto max-w-5xl px-6 py-24">
        <h2 className="mb-12 text-center text-3xl font-bold text-white">
          Everything your shop needs
        </h2>
        <div className="grid gap-6 sm:grid-cols-2">
          <FeatureCard
            icon={<MessageSquare className="h-8 w-8" />}
            title="Query Manuals"
            description="Ask questions in plain language. Get answers with page references, confidence scores, and spec values — backed by your actual service manuals."
          />
          <FeatureCard
            icon={<BookOpen className="h-8 w-8" />}
            title="Troubleshoot"
            description="Describe the problem, get step-by-step diagnostic procedures with safety warnings and torque specs. AI-powered but manual-grounded."
          />
          <FeatureCard
            icon={<Image className="h-8 w-8" />}
            title="Interactive Schematics"
            description="Hydraulic and electrical diagrams come alive. Click components, trace flows, switch operating states. AI-annotated with part locations."
          />
          <FeatureCard
            icon={<GraduationCap className="h-8 w-8" />}
            title="Train Your Team"
            description="Teach-then-troubleshoot mode builds understanding before fixing. Auto-generated learning paths, quizzes, and progress tracking."
          />
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-800 py-8 text-center text-sm text-slate-500">
        <p>
          ManualWorx by{" "}
          <span className="text-slate-400">Fulcrum Systems</span> — Leverage
          for the climb.
        </p>
      </footer>
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
    <div className="group rounded-xl border border-slate-700 bg-slate-800/50 p-6 transition hover:border-slate-600 hover:bg-slate-800">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-600/10 text-emerald-500 transition group-hover:bg-emerald-600/20">
        {icon}
      </div>
      <h3 className="mb-2 text-lg font-semibold text-white">{title}</h3>
      <p className="text-sm leading-relaxed text-slate-400">{description}</p>
    </div>
  );
}
