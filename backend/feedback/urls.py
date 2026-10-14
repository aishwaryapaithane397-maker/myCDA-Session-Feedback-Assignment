from django.urls import path

from . import views

urlpatterns = [
    path("", views.FeedbackCreateView.as_view(), name="feedback-create"),
    path("my/", views.MyFeedbackListView.as_view(), name="feedback-my"),
    path(
        "eligible/",
        views.EligibleSessionsView.as_view(),
        name="feedback-eligible",
    ),
    path(
        "instructor-summary/",
        views.InstructorSummaryView.as_view(),
        name="feedback-instructor-summary",
    ),
]
