"use client";

// =============================================================================
// DevBrain AI — Progress Heatmap
// GitHub-style contribution grid for the past 30 days of challenge activity.
// Built with plain divs + Tailwind — no chart library needed.
// =============================================================================

import type { DailyActivity } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProgressHeatmapProps {
  /** 30-day activity array from /progress/dashboard */
  data: DailyActivity[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a full 30-day calendar from today backwards, merging in activity data. */
function buildCalendar(data: DailyActivity[]): {
  date: string;
  dayLabel: string;
  total: number;
  details: Pick<DailyActivity, "challenges_solved" | "reviews_submitted" | "interview_sessions">;
}[] {
  const activityMap: Record<string, DailyActivity> = {};
  for (const d of data) {
    activityMap[d.date] = d;
  }

  const result = [];
  const today  = new Date();

  for (let i = 29; i >= 0; i--) {
    const d    = new Date(today);
    d.setDate(today.getDate() - i);
    const iso  = d.toISOString().split("T")[0]; // "YYYY-MM-DD"
    const activity = activityMap[iso];

    result.push({
      date: iso,
      dayLabel: d.toLocaleDateString("en-US", { month: "short", day: "numeric" }),
      total: activity?.total_activity ?? 0,
      details: {
        challenges_solved:    activity?.challenges_solved   ?? 0,
        reviews_submitted:    activity?.reviews_submitted   ?? 0,
        interview_sessions:   activity?.interview_sessions  ?? 0,
      },
    });
  }
  return result;
}

/** Map activity total to a Tailwind background class (0 → 5+). */
function activityToColorClass(total: number): string {
  if (total === 0)  return "bg-[#1a1d2e] border-[#2d3148]";
  if (total === 1)  return "bg-[#22c55e]/20 border-[#22c55e]/20";
  if (total === 2)  return "bg-[#22c55e]/40 border-[#22c55e]/30";
  if (total <= 4)   return "bg-[#22c55e]/65 border-[#22c55e]/50";
  return              "bg-[#22c55e]    border-[#22c55e]";
}

// ---------------------------------------------------------------------------
// Tooltip (pure CSS — hover:group approach)
// ---------------------------------------------------------------------------

function HeatmapCell({
  date,
  dayLabel,
  total,
  details,
}: ReturnType<typeof buildCalendar>[number]) {
  const colorClass = activityToColorClass(total);

  const tooltipLines = [
    dayLabel,
    total === 0
      ? "No activity"
      : `${total} action${total !== 1 ? "s" : ""}`,
    ...(details.challenges_solved   > 0 ? [`${details.challenges_solved} challenge${details.challenges_solved !== 1 ? "s" : ""}`]   : []),
    ...(details.reviews_submitted   > 0 ? [`${details.reviews_submitted} review${details.reviews_submitted !== 1 ? "s" : ""}`]     : []),
    ...(details.interview_sessions  > 0 ? [`${details.interview_sessions} interview${details.interview_sessions !== 1 ? "s" : ""}`] : []),
  ];

  return (
    <div className="relative group">
      <div
        className={`
          w-[28px] h-[28px] rounded-[4px] border cursor-pointer
          transition-transform duration-100 hover:scale-110
          ${colorClass}
        `}
        aria-label={`${dayLabel}: ${total} activities`}
      />
      {/* Tooltip */}
      <div
        className="
          absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20
          bg-[#1a1d2e] border border-[#2d3148] rounded-lg px-2.5 py-2
          text-xs text-gray-300 whitespace-nowrap shadow-xl
          pointer-events-none
          opacity-0 group-hover:opacity-100 transition-opacity duration-150
        "
      >
        {tooltipLines.map((line, i) => (
          <p key={i} className={i === 0 ? "font-semibold text-white mb-0.5" : "text-gray-400"}>
            {line}
          </p>
        ))}
        {/* Arrow */}
        <div className="absolute top-full left-1/2 -translate-x-1/2
                        border-4 border-transparent border-t-[#2d3148]" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function ProgressHeatmap({
  data,
  className = "",
}: ProgressHeatmapProps) {
  const calendar = buildCalendar(data);
  const totalActivity = calendar.reduce((s, d) => s + d.total, 0);
  const activeDays    = calendar.filter((d) => d.total > 0).length;

  // Split 30 days into 5 weeks of 6 days (for a compact grid)
  // We'll just render a single row of 30 for simplicity, scrollable on mobile.
  return (
    <div className={className}>
      {/* Month labels (first day of each "row-of-7") */}
      <div className="flex gap-1 mb-1 overflow-x-auto pb-1">
        {calendar.map((day) => (
          <HeatmapCell key={day.date} {...day} />
        ))}
      </div>

      {/* Legend + summary */}
      <div className="flex items-center justify-between mt-3 flex-wrap gap-2">
        {/* Summary */}
        <p className="text-xs text-gray-500">
          <span className="text-white font-medium">{activeDays}</span> active days,{" "}
          <span className="text-white font-medium">{totalActivity}</span> total actions in the last 30 days
        </p>

        {/* Intensity legend */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-600">Less</span>
          {[0, 1, 2, 3, 5].map((v) => (
            <div
              key={v}
              className={`w-3.5 h-3.5 rounded-[3px] border ${activityToColorClass(v)}`}
            />
          ))}
          <span className="text-xs text-gray-600">More</span>
        </div>
      </div>
    </div>
  );
}