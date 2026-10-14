"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import type { EligibleSession, SessionFeedback } from "@/lib/types";
import DashboardCard from "./DashboardCard";

interface SubmitFeedbackCardProps {
  onSubmitted?: (feedback: SessionFeedback) => void;
}

const RATINGS = [1, 2, 3, 4, 5] as const;

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function SubmitFeedbackCard({
  onSubmitted,
}: SubmitFeedbackCardProps) {
  const { user } = useAuth();
  const isParent = user?.role === "parent";

  const [eligible, setEligible] = useState<EligibleSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [formError, setFormError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [selectedStudentId, setSelectedStudentId] = useState<number | "">("");
  const [sessionId, setSessionId] = useState<number | "">("");
  const [ratingClarity, setRatingClarity] = useState(3);
  const [ratingEngagement, setRatingEngagement] = useState(3);
  const [ratingPace, setRatingPace] = useState(3);
  const [note, setNote] = useState("");

  const linkedStudents = useMemo(() => {
    if (!user?.family_links) return [];
    return user.family_links.map((link) => ({
      id: link.student,
      name: link.student_display.display_name,
    }));
  }, [user]);

  const loadEligible = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const query =
        isParent && selectedStudentId
          ? `?student_id=${selectedStudentId}`
          : "";
      const data = await api.get<EligibleSession[]>(
        `/feedback/eligible/${query}`
      );
      setEligible(data);
      if (data.length > 0) {
        setSessionId((current) =>
          current && data.some((s) => s.id === current) ? current : data[0].id
        );
      } else {
        setSessionId("");
      }
    } catch {
      setError("Could not load eligible sessions.");
      setEligible([]);
    } finally {
      setLoading(false);
    }
  }, [user, isParent, selectedStudentId]);

  useEffect(() => {
    if (isParent && linkedStudents.length > 0 && selectedStudentId === "") {
      setSelectedStudentId(linkedStudents[0].id);
      return;
    }
    loadEligible();
  }, [isParent, linkedStudents, selectedStudentId, loadEligible]);

  const selectedSession = eligible.find((s) => s.id === sessionId);

  const resetRatings = () => {
    setRatingClarity(3);
    setRatingEngagement(3);
    setRatingPace(3);
    setNote("");
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!sessionId || !user) return;

    setFormError("");
    setSuccess("");
    setSubmitting(true);

    const studentId = isParent
      ? Number(selectedStudentId)
      : selectedSession?.student_id ?? user.id;

    const optimistic: SessionFeedback = {
      id: -Date.now(),
      session: Number(sessionId),
      session_display: {
        id: Number(sessionId),
        class_name: selectedSession?.class_name ?? "Session",
        scheduled_date: selectedSession?.scheduled_date ?? new Date().toISOString(),
        status: "completed",
        topic: selectedSession?.topic ?? "",
      },
      student: studentId,
      student_display: {
        id: studentId,
        display_name:
          selectedSession?.student_display ||
          user.display_name ||
          "Student",
        role: "student",
      },
      submitter: user.id,
      submitter_display: {
        id: user.id,
        display_name: user.display_name,
        role: user.role,
      },
      rating_clarity: ratingClarity,
      rating_engagement: ratingEngagement,
      rating_pace: ratingPace,
      note,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    // Optimistic: remove session from eligible list immediately.
    const previousEligible = eligible;
    setEligible((prev) => prev.filter((s) => s.id !== sessionId));
    onSubmitted?.(optimistic);

    try {
      const body: Record<string, unknown> = {
        session: Number(sessionId),
        rating_clarity: ratingClarity,
        rating_engagement: ratingEngagement,
        rating_pace: ratingPace,
        note,
      };
      if (isParent) {
        body.student = studentId;
      }

      const created = await api.post<SessionFeedback>("/feedback/", body);
      setSuccess("Feedback submitted.");
      resetRatings();
      onSubmitted?.(created);
      await loadEligible();
    } catch (err) {
      // Roll back optimistic UI
      setEligible(previousEligible);
      if (err instanceof ApiError) {
        const detail =
          (typeof err.body.detail === "string" && err.body.detail) ||
          (typeof err.body.non_field_errors === "object" &&
            Array.isArray(err.body.non_field_errors) &&
            String(err.body.non_field_errors[0])) ||
          (typeof err.body.session === "object" &&
            Array.isArray(err.body.session) &&
            String(err.body.session[0])) ||
          (typeof err.body.student === "object" &&
            Array.isArray(err.body.student) &&
            String(err.body.student[0])) ||
          "Could not submit feedback.";
        setFormError(detail);
      } else {
        setFormError("Could not submit feedback.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <DashboardCard title="Submit Feedback">
        <p className="text-sm text-gray-400">Loading eligible sessions...</p>
      </DashboardCard>
    );
  }

  if (error) {
    return (
      <DashboardCard title="Submit Feedback">
        <p className="text-sm text-red-500">{error}</p>
      </DashboardCard>
    );
  }

  return (
    <DashboardCard
      title="Submit Feedback"
      subtitle="Completed sessions from the last 30 days"
    >
      {eligible.length === 0 ? (
        <p className="text-sm text-gray-500">
          No sessions are currently eligible for feedback.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          {isParent && (
            <label className="block">
              <span className="text-xs font-medium text-gray-600">Student</span>
              <select
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                value={selectedStudentId}
                onChange={(e) =>
                  setSelectedStudentId(
                    e.target.value ? Number(e.target.value) : ""
                  )
                }
                required
              >
                {linkedStudents.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="block">
            <span className="text-xs font-medium text-gray-600">Session</span>
            <select
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              value={sessionId}
              onChange={(e) =>
                setSessionId(e.target.value ? Number(e.target.value) : "")
              }
              required
            >
              {eligible.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.class_name} — {formatDate(session.scheduled_date)}
                  {session.topic ? ` (${session.topic})` : ""}
                </option>
              ))}
            </select>
          </label>

          <RatingField
            label="Clarity"
            value={ratingClarity}
            onChange={setRatingClarity}
          />
          <RatingField
            label="Engagement"
            value={ratingEngagement}
            onChange={setRatingEngagement}
          />
          <RatingField
            label="Pace"
            value={ratingPace}
            onChange={setRatingPace}
          />

          <label className="block">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-gray-600">
                Optional note
              </span>
              <span className="text-xs text-gray-400">{note.length}/500</span>
            </div>
            <textarea
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              rows={3}
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="What went well? What could improve?"
            />
          </label>

          {formError && (
            <p className="text-sm text-red-500">{formError}</p>
          )}
          {success && (
            <p className="text-sm text-green-600">{success}</p>
          )}

          <button
            type="submit"
            disabled={submitting || !sessionId}
            className="rounded-md bg-cda-navy px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {submitting ? "Submitting..." : "Submit feedback"}
          </button>
        </form>
      )}
    </DashboardCard>
  );
}

function RatingField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600">{label}</span>
        <span className="text-xs text-gray-500">{value}/5</span>
      </div>
      <input
        type="range"
        min={1}
        max={5}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-cda-navy"
        list={`${label}-ticks`}
      />
      <datalist id={`${label}-ticks`}>
        {RATINGS.map((rating) => (
          <option key={rating} value={rating} />
        ))}
      </datalist>
    </div>
  );
}
