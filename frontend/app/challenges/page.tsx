"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import { generateChallenge, submitChallenge, getChallengeHistory } from "@/lib/api";
import type { Challenge } from "@/lib/types";

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-gray-500 text-sm">
      Loading editor…
    </div>
  ),
});

type TestResult = {
  passed: boolean;
  input?: string;
  expected?: string;
  got?: string;
  error?: string;
};

type SubmitResult = {
  passed: boolean;
  test_results: TestResult[];
  feedback: string;
  score?: number;
};

type HistoryEntry = {
  id: string;
  title: string;
  language: string;
  passed: boolean;
  score?: number;
  created_at: string;
};

function DiffBadge({ difficulty }: { difficulty: string }) {
  const map: Record<string, { bg: string; color: string }> = {
    easy: { bg: "#22c55e22", color: "#22c55e" },
    medium: { bg: "#f59e0b22", color: "#f59e0b" },
    hard: { bg: "#ef444422", color: "#ef4444" },
  };
  const s = map[difficulty?.toLowerCase()] ?? map.medium;
  return (
    <span
      className="text-xs font-semibold px-2.5 py-1 rounded-full capitalize"
      style={s}
    >
      {difficulty}
    </span>
  );
}

function TestCaseRow({ result, i }: { result: TestResult; i: number }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-[#2d3148] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-[#2d3148]/30 transition-colors"
      >
        <span
          className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
            result.passed
              ? "bg-[#22c55e22] text-[#22c55e]"
              : "bg-[#ef444422] text-[#ef4444]"
          }`}
        >
          {result.passed ? "✓" : "✗"}
        </span>
        <span className="text-gray-300">Test case {i + 1}</span>
        <span className="ml-auto text-gray-600 text-xs">
          {open ? "▴" : "▾"}
        </span>
      </button>
      {open && (
        <div className="px-4 pb-3 space-y-1.5 text-xs font-mono">
          {result.input && (
            <div>
              <span className="text-gray-500">Input: </span>
              <span className="text-gray-300">{result.input}</span>
            </div>
          )}
          {result.expected && (
            <div>
              <span className="text-gray-500">Expected: </span>
              <span className="text-[#22c55e]">{result.expected}</span>
            </div>
          )}
          {result.got && (
            <div>
              <span className="text-gray-500">Got: </span>
              <span
                className={result.passed ? "text-[#22c55e]" : "text-[#ef4444]"}
              >
                {result.got}
              </span>
            </div>
          )}
          {result.error && (
            <div>
              <span className="text-[#ef4444]">{result.error}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChallengesPage() {
  const router = useRouter();
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState("");
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("devbrain_token")) {
      router.push("/");
      return;
    }
    setHistoryLoading(true);
    getChallengeHistory()
      .then((h) => setHistory(h ?? []))
      .catch(() => setHistory([]))
      .finally(() => setHistoryLoading(false));
  }, [router]);

  const handleGenerate = async () => {
    setGenerating(true);
    setResult(null);
    try {
      const c = await generateChallenge();
      setChallenge(c);
      setCode(c.starter_code ?? "");
    } finally {
      setGenerating(false);
    }
  };

  const handleSubmit = async () => {
    if (!challenge || !code.trim()) return;
    setSubmitting(true);
    setResult(null);
    try {
      const r = await submitChallenge(challenge.id, code);
      setResult(r);
      // Refresh history
      const h = await getChallengeHistory().catch(() => []);
      setHistory(h ?? []);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Daily Challenges
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            AI-generated problems targeting your weak areas
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-5 py-2.5 bg-[#6366f1] hover:bg-[#5558e3] text-white font-semibold text-sm rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {generating ? (
            <>
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Generating…
            </>
          ) : (
            "⚡ Get Today's Challenge"
          )}
        </button>
      </div>

      {challenge && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* ── Left: Problem description ── */}
          <div className="space-y-4">
            <div className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl p-6 shadow-[0_0_15px_rgba(99,102,241,0.1)]">
              <div className="flex items-start justify-between gap-3 mb-4">
                <h2 className="text-white font-bold text-lg">
                  {challenge.title}
                </h2>
                <DiffBadge difficulty={challenge.difficulty ?? "medium"} />
              </div>
              <p className="text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                {challenge.description}
              </p>
            </div>

            {/* Constraints */}
            {challenge.constraints?.length > 0 && (
              <details className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl overflow-hidden">
                <summary className="px-5 py-3.5 text-sm font-semibold text-white cursor-pointer hover:bg-[#2d3148]/30 transition-colors flex items-center justify-between">
                  <span>📏 Constraints</span>
                  <span className="text-gray-500 text-xs">click to expand</span>
                </summary>
                <div className="px-5 pb-4">
                  <ul className="space-y-1.5">
                    {challenge.constraints.map((c: string, i: number) => (
                      <li key={i} className="text-gray-400 text-sm flex gap-2">
                        <span className="text-[#6366f1]">•</span>
                        {c}
                      </li>
                    ))}
                  </ul>
                </div>
              </details>
            )}

            {/* Examples */}
            {challenge.examples?.length > 0 && (
              <details className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl overflow-hidden" open>
                <summary className="px-5 py-3.5 text-sm font-semibold text-white cursor-pointer hover:bg-[#2d3148]/30 transition-colors">
                  💡 Examples
                </summary>
                <div className="px-5 pb-4 space-y-3">
                  {challenge.examples.map(
                    (ex: { input: string; output: string; explanation?: string }, i: number) => (
                      <div
                        key={i}
                        className="bg-[#0f1117] rounded-lg p-3 text-xs font-mono"
                      >
                        <p>
                          <span className="text-gray-500">Input: </span>
                          <span className="text-gray-300">{ex.input}</span>
                        </p>
                        <p>
                          <span className="text-gray-500">Output: </span>
                          <span className="text-[#22c55e]">{ex.output}</span>
                        </p>
                        {ex.explanation && (
                          <p className="text-gray-500 mt-1">{ex.explanation}</p>
                        )}
                      </div>
                    )
                  )}
                </div>
              </details>
            )}

            {/* Submit results */}
            {result && (
              <div
                className={`border rounded-xl p-5 ${
                  result.passed
                    ? "bg-[#22c55e11] border-[#22c55e44]"
                    : "bg-[#ef444411] border-[#ef444444]"
                }`}
              >
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">{result.passed ? "🎉" : "❌"}</span>
                  <span
                    className={`font-bold ${
                      result.passed ? "text-[#22c55e]" : "text-[#ef4444]"
                    }`}
                  >
                    {result.passed ? "All tests passed!" : "Some tests failed"}
                  </span>
                  {result.score != null && (
                    <span className="ml-auto text-sm text-gray-400">
                      Score: {result.score}/100
                    </span>
                  )}
                </div>
                {result.test_results?.length > 0 && (
                  <div className="space-y-2 mb-3">
                    {result.test_results.map((tr, i) => (
                      <TestCaseRow key={i} result={tr} i={i} />
                    ))}
                  </div>
                )}
                {result.feedback && (
                  <div className="bg-[#0f1117] rounded-lg p-3">
                    <p className="text-gray-400 text-xs uppercase tracking-widest mb-1">
                      Grok Feedback
                    </p>
                    <p className="text-gray-300 text-sm leading-relaxed">
                      {result.feedback}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Right: Editor ── */}
          <div className="flex flex-col gap-4">
            <div className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl p-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-[#22c55e]" />
                <span className="text-gray-400 text-xs font-medium uppercase tracking-widest">
                  {challenge.language ?? "python"}
                </span>
              </div>
              <button
                onClick={handleSubmit}
                disabled={submitting || !code.trim()}
                className="px-4 py-2 bg-[#22c55e] hover:bg-[#16a34a] text-white text-sm font-semibold rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {submitting ? (
                  <>
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Running…
                  </>
                ) : (
                  "▶ Submit"
                )}
              </button>
            </div>

            <div className="flex-1 bg-[#1a1d2e] border border-[#2d3148] rounded-xl overflow-hidden shadow-[0_0_15px_rgba(99,102,241,0.1)] min-h-[400px]">
              <MonacoEditor
                language={challenge.language ?? "python"}
                value={code}
                onChange={(v) => setCode(v ?? "")}
                theme="vs-dark"
                options={{
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                  padding: { top: 16, bottom: 16 },
                  readOnly: false,
                }}
              />
            </div>
          </div>
        </div>
      )}

      {!challenge && !generating && (
        <div className="text-center py-16">
          <div className="text-6xl mb-5">⚡</div>
          <p className="text-gray-300 font-semibold text-lg mb-2">
            Ready for a challenge?
          </p>
          <p className="text-gray-500 text-sm">
            Click "Get Today's Challenge" to receive a problem tailored to your weak areas.
          </p>
        </div>
      )}

      {/* ── History table ── */}
      {(history.length > 0 || historyLoading) && (
        <div className="bg-[#1a1d2e] border border-[#2d3148] rounded-xl overflow-hidden shadow-[0_0_15px_rgba(99,102,241,0.1)]">
          <div className="px-6 py-4 border-b border-[#2d3148]">
            <h2 className="text-white font-semibold flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#f59e0b]" />
              Challenge History
            </h2>
          </div>
          {historyLoading ? (
            <div className="p-6 space-y-3">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="h-4 bg-[#2d3148] rounded animate-pulse"
                />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#2d3148]">
                    {["Challenge", "Language", "Status", "Score", "Date"].map(
                      (h) => (
                        <th
                          key={h}
                          className="px-5 py-3 text-left text-xs text-gray-400 uppercase tracking-widest font-medium"
                        >
                          {h}
                        </th>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 10).map((entry) => (
                    <tr
                      key={entry.id}
                      className="border-b border-[#2d3148] last:border-0 hover:bg-[#2d3148]/20 transition-colors"
                    >
                      <td className="px-5 py-3 text-gray-300">{entry.title}</td>
                      <td className="px-5 py-3 text-gray-400 capitalize">
                        {entry.language}
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            entry.passed
                              ? "bg-[#22c55e22] text-[#22c55e]"
                              : "bg-[#ef444422] text-[#ef4444]"
                          }`}
                        >
                          {entry.passed ? "Passed" : "Failed"}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-400">
                        {entry.score != null ? `${entry.score}/100` : "—"}
                      </td>
                      <td className="px-5 py-3 text-gray-500 text-xs">
                        {new Date(entry.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}