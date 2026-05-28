"use client";

// =============================================================================
// DevBrain AI — Landing Page
// Hero + three feature cards + "Connect GitHub" CTA.
// Redirects to /dashboard if already authenticated.
// =============================================================================

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Github,
  Zap,
  GitBranch,
  Brain,
  Map,
  ScanEye,
  ArrowRight,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { isAuthenticated, getLoginUrl } from "@/lib/api";

// ---------------------------------------------------------------------------
// Feature cards data
// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: GitBranch,
    title: "GitHub Analysis",
    description:
      "We scan every repository you've touched to build an honest, evidence-based skill profile — no self-reporting bias.",
    accent: "#6366f1",
    badge: "Auto-detected",
    badgeColor: "badge-indigo",
  },
  {
    icon: ScanEye,
    title: "AI Code Review",
    description:
      "Submit any snippet. Our LangGraph agent loops back until it achieves 75%+ quality confidence before delivering feedback.",
    accent: "#22c55e",
    badge: "Self-reflective",
    badgeColor: "badge-green",
  },
  {
    icon: Map,
    title: "Personalized Roadmap",
    description:
      "Your target role + actual skill gaps generate a week-by-week learning plan — not a generic curriculum.",
    accent: "#f59e0b",
    badge: "Role-specific",
    badgeColor: "badge-amber",
  },
] as const;

const STATS = [
  { value: "94%", label: "Skill Gap Accuracy" },
  { value: "3×",  label: "Faster Preparation"  },
  { value: "50+", label: "Tech Roles Supported" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LandingPage() {
  const router   = useRouter();
  const [loading, setLoading] = useState(false);

  // Redirect logged-in users straight to dashboard
  useEffect(() => {
    if (isAuthenticated()) {
      router.replace("/dashboard");
    }
  }, [router]);

  const handleConnect = async () => {
    setLoading(true);
    try {
      const { auth_url } = await getLoginUrl();
      window.location.href = auth_url;
    } catch {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f1117] overflow-x-hidden">

      {/* ── Nav bar ── */}
      <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between
                         px-6 py-4 border-b border-[#2d3148]/50 bg-[#0f1117]/80 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-[#6366f1] flex items-center justify-center">
            <Brain size={15} className="text-white" />
          </div>
          <span className="font-bold text-white">DevBrain<span className="text-[#6366f1]"> AI</span></span>
        </div>
        <button
          onClick={handleConnect}
          disabled={loading}
          className="btn-primary flex items-center gap-2 text-sm py-2 px-4"
        >
          <Github size={15} />
          Connect GitHub
        </button>
      </header>

      {/* ── Hero ── */}
      <section className="relative flex flex-col items-center text-center pt-36 pb-24 px-6">

        {/* Background radial glow */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px]
                        bg-[#6366f1]/10 rounded-full blur-[120px] pointer-events-none" />

        {/* Badge */}
        <div className="fade-in flex items-center gap-2 px-3 py-1.5 rounded-full
                        bg-[#6366f1]/10 border border-[#6366f1]/30 text-[#818cf8]
                        text-xs font-medium mb-6">
          <Sparkles size={12} />
          Powered by Grok AI + LangGraph
        </div>

        {/* Headline */}
        <h1 className="fade-in text-5xl sm:text-6xl md:text-7xl font-bold leading-[1.08] tracking-tight
                       max-w-3xl mb-6"
            style={{ animationDelay: "0.08s" }}>
          Know Your Real
          <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#6366f1] to-[#818cf8]">
            Skill Gaps
          </span>
        </h1>

        {/* Subheadline */}
        <p className="fade-in text-lg text-gray-400 max-w-xl mb-10 leading-relaxed"
           style={{ animationDelay: "0.16s" }}>
          DevBrain analyzes your GitHub activity to surface exactly where you're strong and where
          you're falling behind — then gives you a plan to close the gap.
        </p>

        {/* CTA buttons */}
        <div className="fade-in flex flex-wrap items-center justify-center gap-4"
             style={{ animationDelay: "0.24s" }}>
          <button
            onClick={handleConnect}
            disabled={loading}
            className="btn-primary flex items-center gap-2.5 text-base px-6 py-3 glow-pulse"
          >
            <Github size={18} />
            {loading ? "Connecting…" : "Connect GitHub — it's free"}
            {!loading && <ArrowRight size={16} />}
          </button>
        </div>

        {/* Stats */}
        <div className="fade-in flex flex-wrap justify-center gap-8 mt-14"
             style={{ animationDelay: "0.32s" }}>
          {STATS.map(({ value, label }) => (
            <div key={label} className="text-center">
              <p className="text-2xl font-bold text-white">{value}</p>
              <p className="text-xs text-gray-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Feature cards ── */}
      <section className="px-6 pb-24 max-w-5xl mx-auto">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold text-white mb-3">Everything you need to level up</h2>
          <p className="text-gray-400">Five AI-powered tools working together around your actual code.</p>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          {FEATURES.map(({ icon: Icon, title, description, accent, badge, badgeColor }) => (
            <div key={title}
                 className="card p-6 hover:border-[#6366f1]/40 transition-all duration-300 group">
              {/* Icon */}
              <div className="w-10 h-10 rounded-lg flex items-center justify-center mb-4 transition-transform group-hover:scale-110"
                   style={{ backgroundColor: `${accent}20` }}>
                <Icon size={20} style={{ color: accent }} />
              </div>

              {/* Badge */}
              <span className={`${badgeColor} mb-3`}>{badge}</span>

              <h3 className="text-base font-semibold text-white mb-2 mt-2">{title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>

        {/* Extra feature row */}
        <div className="grid md:grid-cols-2 gap-5 mt-5">
          <div className="card p-6 flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#ef4444]/10 flex items-center justify-center shrink-0">
              <Zap size={20} className="text-[#ef4444]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white mb-1">Adaptive Mock Interviews</h3>
              <p className="text-sm text-gray-400">
                DSA and system design sessions that adapt to your level in real time.
              </p>
            </div>
          </div>

          <div className="card p-6 flex items-start gap-4">
            <div className="w-10 h-10 rounded-lg bg-[#22c55e]/10 flex items-center justify-center shrink-0">
              <TrendingUp size={20} className="text-[#22c55e]" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white mb-1">Progress Analytics</h3>
              <p className="text-sm text-gray-400">
                Skill deltas, streaks, and exam-readiness score — updated every session.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA footer ── */}
      <section className="relative px-6 pb-24 text-center">
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-[500px] h-[200px] bg-[#6366f1]/8 rounded-full blur-[100px]" />
        </div>
        <div className="relative max-w-xl mx-auto card p-10">
          <h2 className="text-2xl font-bold text-white mb-3">Ready to see your real level?</h2>
          <p className="text-gray-400 mb-6 text-sm">
            Connect GitHub in 30 seconds. No credit card. No manual forms.
          </p>
          <button
            onClick={handleConnect}
            disabled={loading}
            className="btn-primary inline-flex items-center gap-2 px-6 py-3"
          >
            <Github size={17} />
            {loading ? "Connecting…" : "Get started for free"}
            {!loading && <ArrowRight size={15} />}
          </button>
        </div>
      </section>
    </div>
  );
}