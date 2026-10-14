from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import FamilyLink, User
from classes.models import Class, ClassEnrollment, Session

from .models import SessionFeedback


class FeedbackAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        now = timezone.now()

        self.instructor = User.objects.create_user(
            username="instructor1",
            email="instructor1@cda.test",
            password="testpass123",
            role="instructor",
            first_name="Coach",
            last_name="One",
        )
        self.student = User.objects.create_user(
            username="student1",
            email="student1@cda.test",
            password="testpass123",
            role="student",
            first_name="Student",
            last_name="One",
        )
        self.other_student = User.objects.create_user(
            username="student2",
            email="student2@cda.test",
            password="testpass123",
            role="student",
            first_name="Student",
            last_name="Two",
        )
        self.parent = User.objects.create_user(
            username="parent1",
            email="parent1@cda.test",
            password="testpass123",
            role="parent",
            first_name="Parent",
            last_name="One",
        )
        FamilyLink.objects.create(parent=self.parent, student=self.student)

        self.class_obj = Class.objects.create(
            name="Debate 101",
            instructor=self.instructor,
        )
        ClassEnrollment.objects.create(
            class_obj=self.class_obj, student=self.student
        )
        ClassEnrollment.objects.create(
            class_obj=self.class_obj, student=self.other_student
        )

        self.completed = Session.objects.create(
            class_obj=self.class_obj,
            scheduled_date=now - timedelta(days=3),
            status=Session.Status.COMPLETED,
            session_metadata={"duration_minutes": 90, "topic_covered": "LD"},
        )
        self.old_completed = Session.objects.create(
            class_obj=self.class_obj,
            scheduled_date=now - timedelta(days=45),
            status=Session.Status.COMPLETED,
            session_metadata={"duration_minutes": 60, "topic_covered": "PF"},
        )
        self.scheduled = Session.objects.create(
            class_obj=self.class_obj,
            scheduled_date=now + timedelta(days=2),
            status=Session.Status.SCHEDULED,
            session_metadata={"duration_minutes": 60, "topic_covered": "CX"},
        )

    def test_student_can_submit_feedback(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.completed.id,
                "rating_clarity": 5,
                "rating_engagement": 4,
                "rating_pace": 3,
                "note": "Clear explanations",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["submitter"], self.student.id)
        self.assertEqual(response.data["student"], self.student.id)
        self.assertEqual(SessionFeedback.objects.count(), 1)

    def test_duplicate_feedback_rejected(self):
        SessionFeedback.objects.create(
            session=self.completed,
            student=self.student,
            submitter=self.student,
            rating_clarity=4,
            rating_engagement=4,
            rating_pace=4,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.completed.id,
                "rating_clarity": 5,
                "rating_engagement": 5,
                "rating_pace": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_parent_can_submit_for_linked_student(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.completed.id,
                "student": self.student.id,
                "rating_clarity": 4,
                "rating_engagement": 4,
                "rating_pace": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["submitter"], self.parent.id)
        self.assertEqual(response.data["student"], self.student.id)

    def test_parent_cannot_submit_for_unlinked_student(self):
        self.client.force_authenticate(user=self.parent)
        response = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.completed.id,
                "student": self.other_student.id,
                "rating_clarity": 4,
                "rating_engagement": 4,
                "rating_pace": 4,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reject_non_completed_and_stale_sessions(self):
        self.client.force_authenticate(user=self.student)

        scheduled_resp = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.scheduled.id,
                "rating_clarity": 3,
                "rating_engagement": 3,
                "rating_pace": 3,
            },
            format="json",
        )
        self.assertEqual(scheduled_resp.status_code, status.HTTP_400_BAD_REQUEST)

        old_resp = self.client.post(
            "/api/v1/feedback/",
            {
                "session": self.old_completed.id,
                "rating_clarity": 3,
                "rating_engagement": 3,
                "rating_pace": 3,
            },
            format="json",
        )
        self.assertEqual(old_resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instructor_summary_is_anonymized_and_weighted(self):
        SessionFeedback.objects.create(
            session=self.completed,
            student=self.student,
            submitter=self.student,
            rating_clarity=5,
            rating_engagement=5,
            rating_pace=5,
        )
        SessionFeedback.objects.create(
            session=self.completed,
            student=self.other_student,
            submitter=self.other_student,
            rating_clarity=3,
            rating_engagement=3,
            rating_pace=3,
        )

        self.client.force_authenticate(user=self.instructor)
        response = self.client.get("/api/v1/feedback/instructor-summary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        body = response.data
        self.assertEqual(body["feedback_count"], 2)
        self.assertNotIn("student", body)
        self.assertNotIn("note", body)
        self.assertNotIn("results", body)

        # Session averages: clarity=(5+3)/2=4, same for others; weight=90
        self.assertEqual(body["weighted_averages"]["clarity"], 4.0)
        self.assertEqual(body["weighted_averages"]["overall"], 4.0)

        # Ensure no identity leakage in stringified payload
        serialized = str(body)
        self.assertNotIn(self.student.username, serialized)
        self.assertNotIn("Clear", serialized)
