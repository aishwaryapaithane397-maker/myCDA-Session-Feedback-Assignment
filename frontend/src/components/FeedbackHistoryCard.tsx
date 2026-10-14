"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { PaginatedResponse, SessionFeedback } from "@/lib/types";
import DashboardCard from "./DashboardCard";

interface FeedbackHistoryCardProps {
  refreshKey?: number;
  optimisticItem?: SessionFeedback | null;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function RatingChips({ item }: { item: SessionFeedback }) {
  return (
    <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-600">
      <span>Clarity {item.rating_clarity}/5</span>
      <span>Engagement {item.rating_engagement}/5</span>
      <span>Pace {item.rating_pace}/5</span>
    </div>
  );
}

export default function FeedbackHistoryCard({
  refreshKey = 0,
  optimisticItem = null,
}: FeedbackHistoryCardProps) {
  const { user } = useAuth();
  const [items, setItems] = useState<SessionFeedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .get<PaginatedResponse<SessionFeedback>>("/feedback/my/")
      .then((res) => setItems(res.results))
      .catch(() => setError("Could not load feedback history."))
      .finally(() => setLoading(false));
  }, [refreshKey]);

  const displayItems = useMemo(() => {
    if (!optimisticItem) return items;
    if (items.some((item) => item.id === optimisticItem.id)) return items;
    // Keep optimistic entry until server list refreshes with a real id.
    if (optimisticItem.id < 0) {
      return [optimisticItem, ...items];
    }
    const withoutTemp = items.filter((item) => item.id > 0);
    if (withoutTemp.some((item) => item.id === optimisticItem.id)) {
      return withoutTemp;
    }
    return [optimisticItem, ...withoutTemp];
  }, [items, optimisticItem]);

  if (loading) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-gray-400">Loading...</p>
      </DashboardCard>
    );
  }

  if (error) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-red-500">{error}</p>
      </DashboardCard>
    );
  }

  if (displayItems.length === 0) {
    return (
      <DashboardCard title="Feedback History">
        <p className="text-sm text-gray-500">No feedback submitted yet.</p>
      </DashboardCard>
    );
  }

  if (user?.role === "parent") {
    const grouped = displayItems.reduce<Record<string, SessionFeedback[]>>(
      (acc, item) => {
        const key = item.student_display.display_name;
        if (!acc[key]) acc[key] = [];
        acc[key].push(item);
        return acc;
      },
      {}
    );

    return (
      <DashboardCard
        title="Feedback History"
        subtitle={`${displayItems.length} review${displayItems.length !== 1 ? "s" : ""}`}
        flush
      >
        <div className="divide-y divide-gray-100">
          {Object.entries(grouped).map(([studentName, reviews]) => (
            <div key={studentName} className="px-5 py-3">
              <p className="text-sm font-semibold text-gray-900">{studentName}</p>
              <ul className="mt-2 space-y-3">
                {reviews.map((item) => (
                  <li key={item.id}>
                    <p className="text-sm text-gray-800">
                      {item.session_display.class_name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatDate(item.session_display.scheduled_date)}
                    </p>
                    <RatingChips item={item} />
                    {item.note && (
                      <p className="mt-1 text-xs text-gray-600">{item.note}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </DashboardCard>
    );
  }

  return (
    <DashboardCard
      title="Feedback History"
      subtitle={`${displayItems.length} review${displayItems.length !== 1 ? "s" : ""}`}
      flush
    >
      <ul className="divide-y divide-gray-100">
        {displayItems.map((item) => (
          <li key={item.id} className="px-5 py-3">
            <p className="text-sm font-medium text-gray-900">
              {item.session_display.class_name}
            </p>
            <p className="text-xs text-gray-500">
              {formatDate(item.session_display.scheduled_date)}
            </p>
            <RatingChips item={item} />
            {item.note && (
              <p className="mt-1 text-xs text-gray-600">{item.note}</p>
            )}
          </li>
        ))}
      </ul>
    </DashboardCard>
  );
}
