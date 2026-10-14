from datetime import timedelta

from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import FamilyLink, User
from classes.models import ClassEnrollment, Session
from core.permissions import IsInstructorOrAdmin, IsStudentOrParent

from .models import SessionFeedback
from .serializers import (
    FEEDBACK_WINDOW_DAYS,
    EligibleSessionSerializer,
    InstructorSummarySerializer,
    SessionFeedbackSerializer,
)


def _linked_student_ids(parent):
    return list(
        FamilyLink.objects.filter(parent=parent).values_list(
            "student_id", flat=True
        )
    )


def _compute_instructor_summary(instructor):
    """
    Duration-weighted rolling average over the instructor's last 10
    completed sessions. Returns only anonymized aggregates.
    """
    window_sessions = list(
        Session.objects.filter(
            class_obj__instructor=instructor,
            status=Session.Status.COMPLETED,
        )
        .order_by("-scheduled_date")[:10]
        .prefetch_related(
            Prefetch(
                "feedback_entries",
                queryset=SessionFeedback.objects.all(),
            )
        )
    )

    weighted = {
        "clarity": 0.0,
        "engagement": 0.0,
        "pace": 0.0,
        "overall": 0.0,
    }
    total_weight = 0.0
    feedback_count = 0
    sessions_with_feedback = 0

    for session in window_sessions:
        entries = list(session.feedback_entries.all())
        if not entries:
            continue

        sessions_with_feedback += 1
        feedback_count += len(entries)
        duration = float(session.duration_minutes or 60)
        if duration <= 0:
            duration = 60.0

        avg_clarity = sum(e.rating_clarity for e in entries) / len(entries)
        avg_engagement = sum(e.rating_engagement for e in entries) / len(
            entries
        )
        avg_pace = sum(e.rating_pace for e in entries) / len(entries)
        avg_overall = (avg_clarity + avg_engagement + avg_pace) / 3.0

        weighted["clarity"] += avg_clarity * duration
        weighted["engagement"] += avg_engagement * duration
        weighted["pace"] += avg_pace * duration
        weighted["overall"] += avg_overall * duration
        total_weight += duration

    if total_weight > 0:
        averages = {
            key: round(value / total_weight, 2)
            for key, value in weighted.items()
        }
    else:
        averages = {
            "clarity": None,
            "engagement": None,
            "pace": None,
            "overall": None,
        }

    return {
        "instructor_id": instructor.id,
        "sessions_in_window": len(window_sessions),
        "sessions_with_feedback": sessions_with_feedback,
        "feedback_count": feedback_count,
        "weighted_averages": averages,
        "window_description": (
            "Aggregated, anonymized scores. Duration-weighted rolling "
            "average over the last 10 completed sessions. Individual "
            "reviews, notes, and student identities are never exposed."
        ),
    }


class FeedbackCreateView(generics.CreateAPIView):
    """POST /api/v1/feedback/ — submit session feedback."""

    serializer_class = SessionFeedbackSerializer
    permission_classes = [IsAuthenticated, IsStudentOrParent]


class MyFeedbackListView(generics.ListAPIView):
    """
    GET /api/v1/feedback/my/

    Students see their own submitted feedback.
    Parents see feedback for all linked students.
    """

    serializer_class = SessionFeedbackSerializer
    permission_classes = [IsAuthenticated, IsStudentOrParent]

    def get_queryset(self):
        user = self.request.user
        qs = SessionFeedback.objects.select_related(
            "session",
            "session__class_obj",
            "student",
            "submitter",
            "created_by",
        ).order_by("-created_at")

        if user.role == "student":
            return qs.filter(student=user)
        if user.role == "parent":
            return qs.filter(student_id__in=_linked_student_ids(user))
        return qs.none()


class EligibleSessionsView(generics.ListAPIView):
    """
    GET /api/v1/feedback/eligible/

    Completed sessions within 30 days that the student (or parent's linked
    student) has not yet reviewed. Optional ?student_id= for parents.
    """

    serializer_class = EligibleSessionSerializer
    permission_classes = [IsAuthenticated, IsStudentOrParent]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        user = request.user
        student_id = request.query_params.get("student_id")

        if user.role == "student":
            students = [user]
        else:
            linked_ids = _linked_student_ids(user)
            if student_id is not None:
                try:
                    student_id = int(student_id)
                except (TypeError, ValueError):
                    return Response(
                        {"student_id": "Must be an integer."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if student_id not in linked_ids:
                    return Response(
                        {
                            "student_id": (
                                "You can only request eligible sessions "
                                "for linked students."
                            )
                        },
                        status=status.HTTP_403_FORBIDDEN,
                    )
                students = list(
                    User.objects.filter(id=student_id, role=User.Role.STUDENT)
                )
            else:
                students = list(
                    User.objects.filter(
                        id__in=linked_ids, role=User.Role.STUDENT
                    )
                )

        cutoff = timezone.now() - timedelta(days=FEEDBACK_WINDOW_DAYS)
        payload = []

        for student in students:
            class_ids = ClassEnrollment.objects.filter(
                student=student, is_active=True
            ).values_list("class_obj_id", flat=True)

            already_reviewed = set(
                SessionFeedback.objects.filter(student=student).values_list(
                    "session_id", flat=True
                )
            )

            sessions = (
                Session.objects.filter(
                    class_obj_id__in=class_ids,
                    status=Session.Status.COMPLETED,
                    scheduled_date__gte=cutoff,
                )
                .exclude(id__in=already_reviewed)
                .select_related("class_obj")
                .order_by("-scheduled_date")
            )

            for session in sessions:
                payload.append(
                    {
                        "id": session.id,
                        "class_obj": session.class_obj_id,
                        "class_name": session.class_obj.name,
                        "scheduled_date": session.scheduled_date,
                        "status": session.status,
                        "topic": session.topic,
                        "duration_minutes": session.duration_minutes,
                        "student_id": student.id,
                        "student_display": student.get_display_name(),
                    }
                )

        serializer = self.get_serializer(payload, many=True)
        return Response(serializer.data)


class InstructorSummaryView(APIView):
    """
    GET /api/v1/feedback/instructor-summary/

    Instructors see their own anonymized aggregate.
    Admins may pass ?instructor_id=X.
    """

    permission_classes = [IsAuthenticated, IsInstructorOrAdmin]

    def get(self, request):
        user = request.user
        instructor_id = request.query_params.get("instructor_id")

        if user.role == "admin":
            if instructor_id is None:
                return Response(
                    {
                        "detail": (
                            "Admins must pass instructor_id to view a "
                            "summary."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                instructor = User.objects.get(
                    id=instructor_id, role=User.Role.INSTRUCTOR
                )
            except User.DoesNotExist:
                return Response(
                    {"instructor_id": "Instructor not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            # Instructors can only see their own summary.
            if instructor_id and int(instructor_id) != user.id:
                return Response(
                    {
                        "detail": (
                            "Instructors may only view their own summary."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            instructor = user

        summary = _compute_instructor_summary(instructor)
        serializer = InstructorSummarySerializer(summary)
        return Response(serializer.data)
