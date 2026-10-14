"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { InstructorSummary } from "@/lib/types";
import DashboardCard from "./DashboardCard";

function ScoreBar({ label, value }: { label: string; value: number | null }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / 5) * 100));

  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-gray-700">{label}</span>
        <span className="font-medium text-gray-900">
          {value == null ? "—" : value.toFixed(2)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded bg-gray-100">
        <div
          className="h-full rounded bg-cda-navy transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function InstructorSummaryCard() {
  const [summary, setSummary] = useState<InstructorSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<InstructorSummary>("/feedback/instructor-summary/")
      .then(setSummary)
      .catch(() => setError("Could not load instructor summary."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <DashboardCard title="Session Feedback Summary">
        <p className="text-sm text-gray-400">Loading...</p>
      </DashboardCard>
    );
  }

  if (error || !summary) {
    return (
      <DashboardCard title="Session Feedback Summary">
        <p className="text-sm text-red-500">
          {error || "Summary unavailable."}
        </p>
      </DashboardCard>
    );
  }

  const averages = summary.weighted_averages;

  return (
    <DashboardCard
      title="Session Feedback Summary"
      subtitle="Aggregated & anonymized"
    >
      <p className="mb-4 text-xs text-gray-500">{summary.window_description}</p>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <div className="rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-500">Overall</p>
          <p className="text-xl font-semibold text-cda-navy">
            {averages.overall == null ? "—" : averages.overall.toFixed(2)}
            <span className="text-sm font-normal text-gray-400"> / 5</span>
          </p>
        </div>
        <div className="rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs text-gray-500">Total reviews</p>
          <p className="text-xl font-semibold text-gray-900">
            {summary.feedback_count}
          </p>
        </div>
      </div>

      <div className="space-y-3">
        <ScoreBar label="Clarity" value={averages.clarity} />
        <ScoreBar label="Engagement" value={averages.engagement} />
        <ScoreBar label="Pace" value={averages.pace} />
      </div>

      <p className="mt-4 text-xs text-gray-400">
        Window: last {summary.sessions_in_window} completed sessions ·{" "}
        {summary.sessions_with_feedback} with feedback
      </p>
    </DashboardCard>
  );
}
