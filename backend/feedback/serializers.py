from datetime import timedelta

from django.db import IntegrityError
from django.utils import timezone
from rest_framework import serializers

from accounts.models import FamilyLink, User
from accounts.serializers import UserMinimalSerializer
from classes.models import ClassEnrollment, Session
from core.serializers import BaseModelSerializer

from .models import SessionFeedback


FEEDBACK_WINDOW_DAYS = 30


def _linked_student_ids(parent):
    return set(
        FamilyLink.objects.filter(parent=parent).values_list(
            "student_id", flat=True
        )
    )


def _can_submit_for_student(user, student):
    if user.role == "student":
        return user.id == student.id
    if user.role == "parent":
        return student.id in _linked_student_ids(user)
    return False


def _student_is_enrolled(student, session):
    return ClassEnrollment.objects.filter(
        class_obj_id=session.class_obj_id,
        student=student,
        is_active=True,
    ).exists()


class SessionFeedbackSerializer(BaseModelSerializer):
    """Create + list serializer for SessionFeedback."""

    session_display = serializers.SerializerMethodField(read_only=True)
    student = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.STUDENT),
        required=False,
        allow_null=True,
    )
    student_display = UserMinimalSerializer(source="student", read_only=True)
    submitter_display = UserMinimalSerializer(
        source="submitter", read_only=True
    )

    class Meta:
        model = SessionFeedback
        fields = [
            "id",
            "session",
            "session_display",
            "student",
            "student_display",
            "submitter",
            "submitter_display",
            "rating_clarity",
            "rating_engagement",
            "rating_pace",
            "note",
            "created_at",
            "updated_at",
            "created_by_display",
        ]
        read_only_fields = [
            "id",
            "submitter",
            "created_at",
            "updated_at",
            "created_by_display",
        ]
        # UniqueConstraint on (session, student) would otherwise force
        # `student` to be required before we can default it for students.
        # Uniqueness is enforced in validate() / create() instead.
        validators = []


    def get_session_display(self, obj):
        session = obj.session
        return {
            "id": session.id,
            "class_name": session.class_obj.name,
            "scheduled_date": session.scheduled_date,
            "status": session.status,
            "topic": session.topic,
        }

    def validate_rating_clarity(self, value):
        return self._validate_rating(value)

    def validate_rating_engagement(self, value):
        return self._validate_rating(value)

    def validate_rating_pace(self, value):
        return self._validate_rating(value)

    def _validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError(
                "Rating must be an integer between 1 and 5."
            )
        return value

    def validate_note(self, value):
        if value is None:
            return ""
        if len(value) > 500:
            raise serializers.ValidationError(
                "Note must be at most 500 characters."
            )
        return value

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        session = attrs["session"]

        # Resolve student: students default to self; parents must specify.
        student = attrs.get("student")
        if student is None:
            if user.role == "student":
                student = user
                attrs["student"] = student
            else:
                raise serializers.ValidationError(
                    {
                        "student": (
                            "Parent submitters must specify which linked "
                            "student this feedback is for."
                        )
                    }
                )

        if student.role != User.Role.STUDENT:
            raise serializers.ValidationError(
                {"student": "Feedback student must have the student role."}
            )

        if not _can_submit_for_student(user, student):
            raise serializers.ValidationError(
                {
                    "student": (
                        "You may only submit feedback for yourself or a "
                        "linked student."
                    )
                }
            )

        if session.status != Session.Status.COMPLETED:
            raise serializers.ValidationError(
                {
                    "session": (
                        "Feedback can only be submitted for completed sessions."
                    )
                }
            )

        cutoff = timezone.now() - timedelta(days=FEEDBACK_WINDOW_DAYS)
        if session.scheduled_date < cutoff:
            raise serializers.ValidationError(
                {
                    "session": (
                        "Feedback cannot be submitted for sessions completed "
                        f"more than {FEEDBACK_WINDOW_DAYS} days ago."
                    )
                }
            )

        if not _student_is_enrolled(student, session):
            raise serializers.ValidationError(
                {
                    "student": (
                        "Student must be enrolled in the class for this session."
                    )
                }
            )

        if SessionFeedback.objects.filter(
            session=session, student=student
        ).exists():
            raise serializers.ValidationError(
                "Feedback already submitted for this session."
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["submitter"] = request.user
        try:
            return super().create(validated_data)
        except IntegrityError:
            raise serializers.ValidationError(
                "Feedback already submitted for this session."
            )


class EligibleSessionSerializer(serializers.Serializer):
    """Read-only shape for sessions a user can still review."""

    id = serializers.IntegerField()
    class_obj = serializers.IntegerField()
    class_name = serializers.CharField()
    scheduled_date = serializers.DateTimeField()
    status = serializers.CharField()
    topic = serializers.CharField()
    duration_minutes = serializers.IntegerField()
    student_id = serializers.IntegerField()
    student_display = serializers.CharField()


class InstructorSummarySerializer(serializers.Serializer):
    """
    Anonymized aggregate payload for instructors/admins.

    Intentionally excludes student/submitter identity and raw notes.
    """

    instructor_id = serializers.IntegerField()
    sessions_in_window = serializers.IntegerField()
    sessions_with_feedback = serializers.IntegerField()
    feedback_count = serializers.IntegerField()
    weighted_averages = serializers.DictField(
        child=serializers.FloatField(allow_null=True)
    )
    window_description = serializers.CharField()
