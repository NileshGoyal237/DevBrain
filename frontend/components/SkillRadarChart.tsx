"use client";

// =============================================================================
// DevBrain AI — Skill Radar Chart
// Uses recharts RadarChart. Shows up to 8 skills from the skill profile.
// If delta is provided, renders +/- badge next to each axis label.
// =============================================================================

import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SkillRadarChartProps {
  /** Scores as 0–1 or 0–100 (auto-normalized). */
  skills: Record<string, number>;
  /** Optional 7-day deltas as 0–1 or percentage points (auto-normalized). */
  delta?: Record<string, number>;
  className?: string;
}

// ---------------------------------------------------------------------------
// Normalization — api.ts sends 0–100; legacy paths may send 0–1
// ---------------------------------------------------------------------------

function normalizeScore(score: number): number {
  if (score > 1) return Math.min(score / 100, 1);
  return Math.max(0, Math.min(score, 1));
}

function normalizeDelta(delta: number): number {
  if (Math.abs(delta) > 1) return delta / 100;
  return delta;
}

// ---------------------------------------------------------------------------
// Custom axis label (with optional delta badge)
// ---------------------------------------------------------------------------

function CustomAxisLabel(props: {
  x?: number;
  y?: number;
  payload?: { value: string };
  delta?: Record<string, number>;
}) {
  const { x = 0, y = 0, payload, delta } = props;
  if (!payload) return null;

  const label = payload.value;
  const rawDelta = delta?.[label] ?? null;
  const hasDelta = rawDelta !== null;
  const deltaVal = hasDelta ? normalizeDelta(rawDelta as number) : 0;
  const isPos = deltaVal > 0;
  const isNeg = deltaVal < 0;

  const cx = 175;
  const anchor = x < cx ? "end" : x > cx ? "start" : "middle";
  const deltaStr = hasDelta
    ? `${isPos ? "+" : ""}${(deltaVal * 100).toFixed(1)}%`
    : null;

  const badgeColor = isPos ? "#22c55e" : isNeg ? "#ef4444" : "#6366f1";

  return (
    <g>
      <text
        x={x}
        y={y}
        textAnchor={anchor}
        dominantBaseline="central"
        fill="#d1d5db"
        fontSize={12}
        fontFamily="var(--font-sans, sans-serif)"
        fontWeight={500}
      >
        {label}
      </text>
      {deltaStr && (
        <>
          <rect
            x={anchor === "end" ? x - 38 : x + 4}
            y={y + 10}
            width={34}
            height={14}
            rx={7}
            fill={`${badgeColor}22`}
            stroke={`${badgeColor}55`}
            strokeWidth={1}
          />
          <text
            x={anchor === "end" ? x - 21 : x + 21}
            y={y + 17}
            textAnchor="middle"
            dominantBaseline="central"
            fill={badgeColor}
            fontSize={9}
            fontFamily="var(--font-mono, monospace)"
            fontWeight={600}
          >
            {deltaStr}
          </text>
        </>
      )}
    </g>
  );
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: { skill: string; score: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const { skill, score } = payload[0].payload;
  return (
    <div className="bg-[#1a1d2e] border border-[#2d3148] rounded-lg px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-white">{skill}</p>
      <p className="text-[#818cf8]">{(score * 100).toFixed(0)}%</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function SkillRadarChart({
  skills,
  delta,
  className = "",
}: SkillRadarChartProps) {
  const topSkills = Object.entries(skills)
    .map(([skill, score]) => [skill, normalizeScore(score)] as const)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8);

  if (topSkills.length === 0) {
    return (
      <div
        className={`flex items-center justify-center h-[350px] text-gray-500 text-sm ${className}`}
      >
        No skill data yet. Connect GitHub to analyze your profile.
      </div>
    );
  }

  const data = topSkills.map(([skill, score]) => ({
    skill,
    score: Math.round(score * 100) / 100,
  }));

  return (
    <div className={className}>
      <ResponsiveContainer width="100%" height={350}>
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="65%">
          <PolarGrid
            gridType="polygon"
            stroke="#2d3148"
            strokeOpacity={0.8}
          />
          <PolarAngleAxis
            dataKey="skill"
            tick={(props) => <CustomAxisLabel {...props} delta={delta} />}
            tickLine={false}
          />
          <PolarRadiusAxis
            domain={[0, 1]}
            tick={false}
            axisLine={false}
            tickCount={5}
          />
          <Radar
            name="Skill Level"
            dataKey="score"
            fill="#6366f1"
            stroke="#818cf8"
            fillOpacity={0.4}
            strokeWidth={2}
            dot={{ fill: "#818cf8", r: 3 }}
          />
          <Tooltip content={<CustomTooltip />} />
        </RadarChart>
      </ResponsiveContainer>

      <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
        {data.map(({ skill, score }) => (
          <div key={skill} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2 h-2 rounded-full"
              style={{
                backgroundColor:
                  score >= 0.7
                    ? "#22c55e"
                    : score >= 0.4
                    ? "#f59e0b"
                    : "#ef4444",
              }}
            />
            <span className="text-gray-400">{skill}</span>
            <span className="text-gray-600">{(score * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
