"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import ActiveClassesCard from "@/components/ActiveClassesCard";
import ProfileCard from "@/components/ProfileCard";
import SubmitFeedbackCard from "@/components/SubmitFeedbackCard";
import FeedbackHistoryCard from "@/components/FeedbackHistoryCard";
import InstructorSummaryCard from "@/components/InstructorSummaryCard";
import type { SessionFeedback } from "@/lib/types";

/**
 * myCDA Dashboard
 *
 * Cards are rendered based on the user's role.
 */
export default function DashboardPage() {
  const { user } = useAuth();
  const [historyRefreshKey, setHistoryRefreshKey] = useState(0);
  const [optimisticFeedback, setOptimisticFeedback] =
    useState<SessionFeedback | null>(null);

  if (!user) return null;

  const canSubmitFeedback =
    user.role === "student" || user.role === "parent";
  const canViewInstructorSummary =
    user.role === "instructor" || user.role === "admin";

  const handleSubmitted = (feedback: SessionFeedback) => {
    setOptimisticFeedback(feedback);
    if (feedback.id > 0) {
      setHistoryRefreshKey((key) => key + 1);
    }
  };

  return (
    <div>
      <h1 className="mb-1 text-xl font-semibold text-gray-900">Dashboard</h1>
      <p className="mb-6 text-sm text-gray-500">
        Welcome back, {user.display_name}
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        <ActiveClassesCard />
        <ProfileCard />

        {canSubmitFeedback && (
          <>
            <SubmitFeedbackCard onSubmitted={handleSubmitted} />
            <FeedbackHistoryCard
              refreshKey={historyRefreshKey}
              optimisticItem={optimisticFeedback}
            />
          </>
        )}

        {canViewInstructorSummary && user.role === "instructor" && (
          <InstructorSummaryCard />
        )}

        {user.role === "admin" && (
          <div className="lg:col-span-2">
            <p className="mb-2 text-sm text-gray-500">
              Admins can request an instructor summary via{" "}
              <code className="rounded bg-gray-100 px-1 text-xs">
                GET /api/v1/feedback/instructor-summary/?instructor_id=X
              </code>
              .
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
