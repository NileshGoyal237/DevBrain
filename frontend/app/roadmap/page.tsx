"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getRoadmap, generateRoadmap } from "@/lib/api";
import type { Roadmap } from "@/lib/types";

const TARGET_ROLES = [
  "Frontend Engineer",
  "Backend Engineer",
  "Full Stack Engineer",
  "DevOps / Platform Engineer",
  "ML / AI Engineer",
  "Data Engineer",
  "Mobile Engineer",
  "Security Engineer",
];

type Week = {
  week: number;
  focus: string;
  topics: string[];
  reason?: string;
};

function WeekCard({ week, index }: { week: Week; index: number }) {
  const [expanded, setExpanded] = useState(false);
  const isFirst = index === 0;

  return (
    <div className="flex gap-4">
      {/* Timeline stem */}
      <div className="flex flex-col items-center">
        <div
          className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold shrink-0 border-2"
          style={{
            background: isFirst ? "#6366f1" : "#1a1d2e",
            borderColor: isFirst ? "#6366f1" : "#2d3148",
            color: isFirst ? "white" : "#9ca3af",
          }}
        >
          {week.week}
        </div>
        <div className="flex-1 w-px bg-[#2d3148] mt-1" />
      </div>

      {/* Card */}
      <div className="flex-1 pb-6">
        <div
          className="bg-[#1a1d2e] border rounded-xl p-5 shadow-[0_0_15px_rgba(99,102,241,0.1)]"
          style={{ borderColor: isFirst ? "#6366f133" : "#2d3148" }}
        >
          <div className="flex items-start justify-between gap-3 mb-3">
            <div>
              <p className="text-gray-400 text-xs uppercase tracking-widest font-medium mb-0.5">
                Week {week.week}
              </p>
              <h3 className="text-white font-semibold text-base">{week.focus}</h3>
            </div>
            {isFirst && (
              <span className="text-xs font-semibold px-2 py-1 rounded-full bg-[#6366f122] text-[#6366f1] shrink-0">
                Current
              </span>
            )}
          </div>

          {/* Topic chips */}
          <div className="flex flex-wrap gap-2 mb-3">
            {week.topics?.map((t) => (
              <Link
                key={t}
                href={`/resources?topic=${encodeURIComponent(t)}`}
                className="text-xs px-2.5 py-1.5 bg-[#0f1117] border border-[#2d3148] text-gray-300 rounded-lg hover:border-[#6366f1] hover:text-white transition-colors"
              >
                {t}
              </Link>
            ))}
          </div>

          {/* Reason */}
          {week.reason && (
            <div>
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-[#6366f1] text-xs font-medium hover:underline flex items-center gap-1"
              >
                {expanded ? "▴" : "▾"} Why this week?
              </button>
              {expanded && (
                <p className="text-gray-400 text-xs mt-2 leading-relaxed bg-[#0f1117] rounded-lg px-3 py-2">
                  {week.reason}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function RoadmapPage() {
  const router = useRouter();
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [targetRole, setTargetRole] = useState(TARGET_ROLES[2]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("devbrain_token")) {
      router.push("/");
      return;
    }
    getRoadmap()
      .then(setRoadmap)
      .catch(() => setRoadmap(null))
      .finally(() => setLoading(false));
  }, [router]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError("");
    try {
      const r = await generateRoadmap(targetRole);
      setRoadmap(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="w-10 h-10 border-2 border-[#6366f1] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const weeks: Week[] = roadmap?.weeks ?? [];

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white tracking-tight">
          Learning Roadmap
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Personalized weekly plan based on your skill profile
        </p>
      </div>

      {!roadmap ? (
        /* ── Generate form ── */
        <div className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl p-8 shadow-[0_0_15px_rgba(99,102,241,0.1)] max-w-md">
          <div className="text-4xl mb-5">🗺️</div>
          <h2 className="text-white text-xl font-bold mb-2">
            Generate Your Roadmap
          </h2>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">
            Select your target role and DevBrain will create a personalized
            week-by-week learning plan based on your GitHub skill gaps.
          </p>
          <div className="space-y-4">
            <div>
              <label className="text-gray-400 text-xs uppercase tracking-widest mb-2 block">
                Target Role
              </label>
              <select
                value={targetRole}
                onChange={(e) => setTargetRole(e.target.value)}
                className="w-full bg-[#0f1117] border border-[#2d3148] text-white text-sm rounded-lg px-4 py-2.5 focus:outline-none focus:border-[#6366f1]"
              >
                {TARGET_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            {error && (
              <p className="text-[#ef4444] text-sm bg-[#ef444411] rounded-lg px-4 py-2">
                {error}
              </p>
            )}
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="w-full py-3 bg-[#6366f1] hover:bg-[#5558e3] text-white font-semibold rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {generating ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Generating roadmap…
                </>
              ) : (
                "Generate Roadmap →"
              )}
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* Header info */}
          <div className="bg-[#1a1d2e] border border-[#6366f133] rounded-xl p-5 mb-8 shadow-[0_0_15px_rgba(99,102,241,0.15)] flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-gray-400 text-xs uppercase tracking-widest mb-1">
                Target Role
              </p>
              <p className="text-white font-semibold">{roadmap.target_role}</p>
            </div>
            <div>
              <p className="text-gray-400 text-xs uppercase tracking-widest mb-1">
                Duration
              </p>
              <p className="text-white font-semibold">
                {weeks.length} weeks
              </p>
            </div>
            <button
              onClick={() => setRoadmap(null)}
              className="text-sm text-gray-400 hover:text-white border border-[#2d3148] px-4 py-2 rounded-lg transition-colors"
            >
              Regenerate
            </button>
          </div>

          {/* Timeline */}
          <div>
            {weeks.map((week, i) => (
              <WeekCard key={week.week} week={week} index={i} />
            ))}
            {/* End marker */}
            <div className="flex gap-4">
              <div className="w-9 flex justify-center">
                <div className="w-3 h-3 rounded-full bg-[#22c55e] border-2 border-[#22c55e33]" />
              </div>
              <p className="text-[#22c55e] text-sm font-medium pb-6">
                🎯 Goal reached — {roadmap.target_role}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}