# Design Decisions — Session Feedback

## Data model

`SessionFeedback` lives in the `feedback` app and links:

- `session` → the completed `Session`
- `student` → the student the review is about
- `submitter` → the authenticated user who sent it (student or parent)

Uniqueness is enforced with a DB constraint on `(session, student)`. That matches the spec: a parent cannot create a second review for the same student/session pair.

Ratings are `PositiveSmallIntegerField`s with 1–5 validators. `note` is optional (`blank=True`, max 500). `created_by` is included so the model fits `BaseModelSerializer`’s audit pattern used elsewhere in the project.

## Permission / validation flow

Server-side checks on create:

1. Session must be `completed`
2. Session `scheduled_date` must be within the last 30 days
3. Submitter must be the student, or a parent linked via `FamilyLink`
4. Student must be actively enrolled in the session’s class
5. No existing feedback for `(session, student)`
6. `submitter` is set from `request.user` — never accepted from the body

Parents must send `student`. Students may omit it; it defaults to self.

## Anonymization

`GET /api/v1/feedback/instructor-summary/` returns **only aggregates**:

- weighted averages (clarity / engagement / pace / overall)
- counts for the rolling window
- a short description of the window

It never returns student IDs, names, submitter info, notes, or per-session / per-student breakdowns. That keeps anonymization at the API layer, not just the UI. Hiding fields in the frontend alone would still leak identity to anyone calling the API with an instructor token.

## Weighted rolling average

1. Take the instructor’s **last 10 completed sessions** (by `scheduled_date` desc)
2. For each session that has feedback, compute the mean of each rating dimension across that session’s entries
3. Session overall = mean of the three dimension averages
4. Weight each session’s averages by `session_metadata["duration_minutes"]` (default 60)
5. Final score = `sum(avg * duration) / sum(duration)` over sessions that have feedback

Sessions in the window with zero feedback do not move the average, but they still count toward `sessions_in_window`.

## Extra endpoint: `/feedback/eligible/`

The spec requires a submit UI that lists eligible sessions. Rather than N+1 client calls across classes/sessions/history, I added a small read-only endpoint that applies the same eligibility rules server-side. It is not required by the written API list, but it keeps the frontend simple and the rules consistent.

## Frontend choices

- Reused `DashboardCard`, `api` client, and role-conditional rendering like `ProfileCard`
- Students/parents: submit form + history card
- Instructors: anonymized summary with simple bar visualization
- Optimistic submit: eligible list updates immediately; rolls back if the API errors

## Trade-offs (one-day scope)

- No separate feedback pages/routes — everything sits on the dashboard as the starter UI suggests
- Admins use `?instructor_id=` on the summary API rather than a full admin picker UI
- No edit/delete of feedback (spec is submit + list + aggregate only)
- SQLite-friendly implementation; weighting is done in Python over at most 10 sessions, which is fine at this scale
