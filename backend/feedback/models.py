from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from classes.models import Session


class SessionFeedback(models.Model):
    """
    Structured review for a completed class session.

    Uniqueness is on (session, student): one feedback entry per student
    per session, regardless of whether a parent or the student submitted it.
    """

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="feedback_entries",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_feedback_as_student",
        limit_choices_to={"role": "student"},
    )
    submitter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_feedback_submitted",
    )
    rating_clarity = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How clearly the instructor explained concepts (1-5).",
    )
    rating_engagement = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How engaging the session was (1-5).",
    )
    rating_pace = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Whether the pacing felt right (1-5).",
    )
    note = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student"],
                name="unique_feedback_per_student_per_session",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Feedback for {self.student} on session {self.session_id} "
            f"(clarity={self.rating_clarity})"
        )

    @property
    def average_rating(self):
        return (
            self.rating_clarity + self.rating_engagement + self.rating_pace
        ) / 3.0
