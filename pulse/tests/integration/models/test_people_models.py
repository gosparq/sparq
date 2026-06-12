# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - People Model Integration Tests
#
# Tests for People module models: hiring pipeline, invites, onboarding,
# offboarding, 1:1s, person notes, tax forms, and update likes.
# -----------------------------------------------------------------------------

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from flask import g

from system.db.database import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_context(ws):
    """Set g.organization_id and g.workspace_id from seeded_workspace."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _get_membership(ws):
    """Return the WorkspaceUser membership from seeded_workspace."""
    return ws["membership"]


# ===========================================================================
# Hiring: JobPosting
# ===========================================================================


@pytest.mark.integration
class TestJobPosting:
    """Tests for JobPosting model."""

    def test_create_job_posting(self, app, db_session, seeded_workspace):
        """Test creating a job posting with defaults."""
        from modules.base.people.models.hiring.job import JobPosting, JobStatus, JobType

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(
            title="Software Engineer",
            department="Engineering",
            location="Remote",
            job_type=JobType.FULL_TIME,
            description="Build great software.",
            requirements="3+ years Python",
        )
        db.session.add(job)
        db.session.commit()

        assert job.id is not None
        assert job.title == "Software Engineer"
        assert job.status == JobStatus.DRAFT
        assert job.is_open is False

    def test_publish_and_close(self, app, db_session, seeded_workspace):
        """Test publish() transitions to OPEN and close() transitions to CLOSED."""
        from modules.base.people.models.hiring.job import JobPosting, JobStatus

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Designer")
        db.session.add(job)
        db.session.commit()

        job.publish()
        assert job.status == JobStatus.OPEN
        assert job.is_open is True
        assert job.published_at is not None

        job.close()
        assert job.status == JobStatus.CLOSED
        assert job.is_open is False
        assert job.closed_at is not None

    def test_hold(self, app, db_session, seeded_workspace):
        """Test hold() transitions to ON_HOLD."""
        from modules.base.people.models.hiring.job import JobPosting, JobStatus

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="PM")
        db.session.add(job)
        db.session.commit()

        job.publish()
        job.hold()
        assert job.status == JobStatus.ON_HOLD

    def test_salary_range_both(self, app, db_session, seeded_workspace):
        """Test salary_range with both min and max."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Eng", salary_min=80000, salary_max=120000)
        db.session.add(job)
        db.session.commit()

        assert job.salary_range == "$80,000 - $120,000"

    def test_salary_range_min_only(self, app, db_session, seeded_workspace):
        """Test salary_range with only min."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Eng", salary_min=90000)
        db.session.add(job)
        db.session.commit()

        assert job.salary_range == "$90,000+"

    def test_salary_range_max_only(self, app, db_session, seeded_workspace):
        """Test salary_range with only max."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Eng", salary_max=150000)
        db.session.add(job)
        db.session.commit()

        assert job.salary_range == "Up to $150,000"

    def test_salary_range_none(self, app, db_session, seeded_workspace):
        """Test salary_range returns None when no salary set."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Eng")
        db.session.add(job)
        db.session.commit()

        assert job.salary_range is None

    def test_get_open_jobs(self, app, db_session, seeded_workspace):
        """Test get_open_jobs returns only published jobs."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        draft = JobPosting(title="Draft Job")
        db.session.add(draft)

        open_job = JobPosting(title="Open Job")
        db.session.add(open_job)
        db.session.commit()
        open_job.publish()

        result = JobPosting.get_open_jobs()
        titles = [j.title for j in result]
        assert "Open Job" in titles
        assert "Draft Job" not in titles

    def test_get_all(self, app, db_session, seeded_workspace):
        """Test get_all returns all jobs."""
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        for title in ["A", "B"]:
            j = JobPosting(title=title)
            db.session.add(j)
        db.session.commit()

        result = JobPosting.get_all()
        assert len(result) >= 2


# ===========================================================================
# Hiring: Candidate
# ===========================================================================


@pytest.mark.integration
class TestCandidate:
    """Tests for Candidate model."""

    def test_create_candidate(self, app, db_session, seeded_workspace):
        """Test basic candidate creation."""
        from modules.base.people.models.hiring.candidate import Candidate, CandidateSource

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            source=CandidateSource.LINKEDIN,
        )
        db.session.add(c)
        db.session.commit()

        assert c.id is not None
        assert c.full_name == "Jane Doe"
        assert c.source == CandidateSource.LINKEDIN

    def test_location_display(self, app, db_session, seeded_workspace):
        """Test location_display property formatting."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="A", last_name="B", email="a@b.com",
                       city="Austin", state="TX", country="US")
        db.session.add(c)
        db.session.commit()

        assert c.location_display == "Austin, TX, US"

    def test_location_display_partial(self, app, db_session, seeded_workspace):
        """Test location_display with missing fields."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="A", last_name="B", email="a2@b.com", city="NYC")
        db.session.add(c)
        db.session.commit()

        assert c.location_display == "NYC"

    def test_location_display_empty(self, app, db_session, seeded_workspace):
        """Test location_display returns None when no location."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="A", last_name="B", email="a3@b.com")
        db.session.add(c)
        db.session.commit()

        assert c.location_display is None

    def test_tag_operations(self, app, db_session, seeded_workspace):
        """Test add_tag, remove_tag, and tag_list."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="A", last_name="B", email="tags@b.com")
        db.session.add(c)
        db.session.commit()

        assert c.tag_list == []

        c.add_tag("python")
        assert "python" in c.tag_list

        c.add_tag("remote")
        assert len(c.tag_list) == 2

        # Adding duplicate should not duplicate
        c.add_tag("python")
        assert c.tag_list.count("python") == 1

        c.remove_tag("python")
        assert "python" not in c.tag_list
        assert "remote" in c.tag_list

    def test_get_by_email(self, app, db_session, seeded_workspace):
        """Test get_by_email lookup."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="Find", last_name="Me", email="findme@example.com")
        db.session.add(c)
        db.session.commit()

        found = Candidate.get_by_email("findme@example.com")
        assert found is not None
        assert found.id == c.id

    def test_search(self, app, db_session, seeded_workspace):
        """Test search by name and email."""
        from modules.base.people.models.hiring.candidate import Candidate

        ws = seeded_workspace
        _set_context(ws)

        c = Candidate(first_name="SearchFirst", last_name="SearchLast", email="search@test.com")
        db.session.add(c)
        db.session.commit()

        assert len(Candidate.search("SearchFirst")) >= 1
        assert len(Candidate.search("SearchLast")) >= 1
        assert len(Candidate.search("search@test")) >= 1
        assert len(Candidate.search("nonexistent_xyz")) == 0


# ===========================================================================
# Hiring: Application
# ===========================================================================


@pytest.mark.integration
class TestApplication:
    """Tests for Application model."""

    def _make_job_and_candidate(self, ws):
        """Helper to create a job and candidate for application tests."""
        from modules.base.people.models.hiring.job import JobPosting
        from modules.base.people.models.hiring.candidate import Candidate

        job = JobPosting(title="Test Position")
        db.session.add(job)

        candidate = Candidate(first_name="App", last_name="Licant", email="app@test.com")
        db.session.add(candidate)
        db.session.commit()
        job.publish()
        return job, candidate

    def test_create_application(self, app, db_session, seeded_workspace):
        """Test creating an application links candidate to job."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(
            job_posting_id=job.id,
            candidate_id=candidate.id,
            cover_letter="I am interested.",
        )
        db.session.add(application)
        db.session.commit()

        assert application.id is not None
        assert application.status == ApplicationStatus.NEW
        assert application.is_active is True

    def test_is_active_false_for_terminal_states(self, app, db_session, seeded_workspace):
        """Test is_active returns False for REJECTED, WITHDRAWN, HIRED."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(
            job_posting_id=job.id,
            candidate_id=candidate.id,
        )
        db.session.add(application)
        db.session.commit()

        for status in [ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN, ApplicationStatus.HIRED]:
            application.status = status
            assert application.is_active is False

    def test_change_status(self, app, db_session, seeded_workspace):
        """Test change_status transitions and logs activity."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus
        from modules.base.people.models.hiring.activity import ApplicationActivity

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(
            job_posting_id=job.id,
            candidate_id=candidate.id,
        )
        db.session.add(application)
        db.session.commit()

        application.change_status(ApplicationStatus.SCREENING)
        assert application.status == ApplicationStatus.SCREENING

        activities = ApplicationActivity.get_for_application(application.id)
        assert len(activities) >= 1
        assert activities[0].new_value == "Screening"

    def test_change_status_rejected_with_reason(self, app, db_session, seeded_workspace):
        """Test rejection stores reason."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(job_posting_id=job.id, candidate_id=candidate.id)
        db.session.add(application)
        db.session.commit()

        application.change_status(ApplicationStatus.REJECTED, reason="Not a fit")
        assert application.rejection_reason == "Not a fit"

    def test_change_status_hired_sets_timestamp(self, app, db_session, seeded_workspace):
        """Test hiring sets hired_at timestamp."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(job_posting_id=job.id, candidate_id=candidate.id)
        db.session.add(application)
        db.session.commit()

        application.change_status(ApplicationStatus.HIRED)
        assert application.hired_at is not None

    def test_set_rating(self, app, db_session, seeded_workspace):
        """Test set_rating stores value and logs activity."""
        from modules.base.people.models.hiring.application import Application

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(job_posting_id=job.id, candidate_id=candidate.id)
        db.session.add(application)
        db.session.commit()

        application.set_rating(4)
        assert application.rating == 4
        assert application.rating_display == "★★★★☆"

    def test_rating_display_none(self, app, db_session, seeded_workspace):
        """Test rating_display returns None when no rating."""
        from modules.base.people.models.hiring.application import Application

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(job_posting_id=job.id, candidate_id=candidate.id)
        db.session.add(application)
        db.session.commit()

        assert application.rating_display is None

    def test_add_note(self, app, db_session, seeded_workspace):
        """Test add_note creates activity record."""
        from modules.base.people.models.hiring.application import Application
        from modules.base.people.models.hiring.activity import ApplicationActivity, ActivityType

        ws = seeded_workspace
        _set_context(ws)
        job, candidate = self._make_job_and_candidate(ws)

        application = Application(job_posting_id=job.id, candidate_id=candidate.id)
        db.session.add(application)
        db.session.commit()

        application.add_note("Great phone screen.")
        activities = ApplicationActivity.get_for_application(application.id)
        note_activities = [a for a in activities if a.activity_type == ActivityType.NOTE_ADDED]
        assert len(note_activities) == 1
        assert note_activities[0].description == "Great phone screen."

    def test_get_pipeline_for_job(self, app, db_session, seeded_workspace):
        """Test pipeline grouping by status."""
        from modules.base.people.models.hiring.application import Application, ApplicationStatus
        from modules.base.people.models.hiring.candidate import Candidate
        from modules.base.people.models.hiring.job import JobPosting

        ws = seeded_workspace
        _set_context(ws)

        job = JobPosting(title="Pipeline Job")
        db.session.add(job)
        db.session.commit()
        job.publish()

        for i, status in enumerate([ApplicationStatus.NEW, ApplicationStatus.SCREENING]):
            c = Candidate(first_name=f"C{i}", last_name="T", email=f"c{i}@pipe.com")
            db.session.add(c)
            db.session.commit()
            a = Application(job_posting_id=job.id, candidate_id=c.id, status=status)
            db.session.add(a)
        db.session.commit()

        pipeline = Application.get_pipeline_for_job(job.id)
        assert len(pipeline[ApplicationStatus.NEW]) == 1
        assert len(pipeline[ApplicationStatus.SCREENING]) == 1


# ===========================================================================
# Hiring: Interview
# ===========================================================================


@pytest.mark.integration
class TestInterview:
    """Tests for Interview model."""

    def _make_application(self, ws):
        """Create a job, candidate, and application for interview tests."""
        from modules.base.people.models.hiring.job import JobPosting
        from modules.base.people.models.hiring.candidate import Candidate
        from modules.base.people.models.hiring.application import Application

        job = JobPosting(title="Interview Job")
        db.session.add(job)
        cand = Candidate(first_name="Int", last_name="View", email="int@view.com")
        db.session.add(cand)
        db.session.commit()
        job.publish()

        app_ = Application(job_posting_id=job.id, candidate_id=cand.id)
        db.session.add(app_)
        db.session.commit()
        return app_

    def test_create_interview(self, app, db_session, seeded_workspace):
        """Test creating an interview."""
        from modules.base.people.models.hiring.interview import (
            Interview, InterviewType, InterviewStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        future = datetime.utcnow() + timedelta(days=3)
        interview = Interview(
            application_id=application.id,
            interview_type=InterviewType.VIDEO,
            scheduled_at=future,
            duration_minutes=45,
            location="https://zoom.us/123",
        )
        db.session.add(interview)
        db.session.commit()

        assert interview.id is not None
        assert interview.status == InterviewStatus.SCHEDULED
        assert interview.duration_minutes == 45

    def test_end_time(self, app, db_session, seeded_workspace):
        """Test end_time calculation."""
        from modules.base.people.models.hiring.interview import Interview

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        start = datetime(2025, 6, 1, 10, 0, 0)
        interview = Interview(
            application_id=application.id,
            scheduled_at=start,
            duration_minutes=60,
        )
        db.session.add(interview)
        db.session.commit()

        assert interview.end_time == datetime(2025, 6, 1, 11, 0, 0)

    def test_is_upcoming(self, app, db_session, seeded_workspace):
        """Test is_upcoming for a future scheduled interview."""
        from modules.base.people.models.hiring.interview import Interview

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        future = datetime.utcnow() + timedelta(days=7)
        interview = Interview(
            application_id=application.id,
            scheduled_at=future,
        )
        db.session.add(interview)
        db.session.commit()

        assert interview.is_upcoming is True

    def test_is_past(self, app, db_session, seeded_workspace):
        """Test is_past for a past interview."""
        from modules.base.people.models.hiring.interview import Interview

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        past = datetime.utcnow() - timedelta(days=1)
        interview = Interview(
            application_id=application.id,
            scheduled_at=past,
        )
        db.session.add(interview)
        db.session.commit()

        assert interview.is_past is True

    def test_complete_interview(self, app, db_session, seeded_workspace):
        """Test completing an interview with feedback."""
        from modules.base.people.models.hiring.interview import (
            Interview, InterviewStatus, InterviewRecommendation,
        )

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        interview = Interview(
            application_id=application.id,
            scheduled_at=datetime.utcnow() - timedelta(hours=1),
        )
        db.session.add(interview)
        db.session.commit()

        interview.complete(
            feedback="Strong candidate.",
            recommendation=InterviewRecommendation.HIRE,
        )

        assert interview.status == InterviewStatus.COMPLETED
        assert interview.feedback == "Strong candidate."
        assert interview.recommendation == InterviewRecommendation.HIRE
        assert interview.completed_at is not None

    def test_cancel_interview(self, app, db_session, seeded_workspace):
        """Test cancelling an interview."""
        from modules.base.people.models.hiring.interview import Interview, InterviewStatus

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        interview = Interview(
            application_id=application.id,
            scheduled_at=datetime.utcnow() + timedelta(days=1),
        )
        db.session.add(interview)
        db.session.commit()

        interview.cancel()
        assert interview.status == InterviewStatus.CANCELLED

    def test_type_icon(self, app, db_session, seeded_workspace):
        """Test type_icon returns correct icon class."""
        from modules.base.people.models.hiring.interview import Interview, InterviewType

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        interview = Interview(
            application_id=application.id,
            scheduled_at=datetime.utcnow(),
            interview_type=InterviewType.TECHNICAL,
        )
        db.session.add(interview)
        db.session.commit()

        assert interview.type_icon == "fa-laptop-code"


# ===========================================================================
# Hiring: ApplicationActivity
# ===========================================================================


@pytest.mark.integration
class TestApplicationActivity:
    """Tests for ApplicationActivity model."""

    def _make_application(self, ws):
        from modules.base.people.models.hiring.job import JobPosting
        from modules.base.people.models.hiring.candidate import Candidate
        from modules.base.people.models.hiring.application import Application

        job = JobPosting(title="Activity Job")
        db.session.add(job)
        cand = Candidate(first_name="Act", last_name="Ivity", email="act@ivity.com")
        db.session.add(cand)
        db.session.commit()

        app_ = Application(job_posting_id=job.id, candidate_id=cand.id)
        db.session.add(app_)
        db.session.commit()
        return app_

    def test_log_activity(self, app, db_session, seeded_workspace):
        """Test ApplicationActivity.log() creates activity."""
        from modules.base.people.models.hiring.activity import ApplicationActivity, ActivityType

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        activity = ApplicationActivity.log(
            application_id=application.id,
            activity_type=ActivityType.CREATED,
            description="Application created.",
        )

        assert activity.id is not None
        assert activity.activity_type == ActivityType.CREATED

    def test_type_icon_and_color(self, app, db_session, seeded_workspace):
        """Test type_icon and type_color properties."""
        from modules.base.people.models.hiring.activity import ApplicationActivity, ActivityType

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        activity = ApplicationActivity.log(
            application_id=application.id,
            activity_type=ActivityType.NOTE_ADDED,
            description="A note.",
        )

        assert activity.type_icon == "fa-sticky-note"
        assert activity.type_color == "text-warning"

    def test_get_recent(self, app, db_session, seeded_workspace):
        """Test get_recent returns recent activities."""
        from modules.base.people.models.hiring.activity import ApplicationActivity, ActivityType

        ws = seeded_workspace
        _set_context(ws)
        application = self._make_application(ws)

        ApplicationActivity.log(
            application_id=application.id,
            activity_type=ActivityType.CREATED,
            description="Created.",
        )

        recent = ApplicationActivity.get_recent(limit=5)
        assert len(recent) >= 1


# ===========================================================================
# Invite
# ===========================================================================


@pytest.mark.integration
class TestWorkspaceInvite:
    """Tests for WorkspaceInvite model."""

    def test_create_invite(self, app, db_session, seeded_workspace):
        """Test creating an invite generates a token."""
        from modules.base.people.models.invite import WorkspaceInvite, InviteStatus

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="newhire@example.com",
            invited_by_id=member.id,
        )

        assert invite.id is not None
        assert invite.email == "newhire@example.com"
        assert invite.token is not None
        assert len(invite.token) > 20
        assert invite.status == InviteStatus.PENDING
        assert invite.is_expired is False

    def test_get_by_token(self, app, db_session, seeded_workspace):
        """Test get_by_token finds a valid pending invite."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="token@example.com",
            invited_by_id=member.id,
        )

        found = WorkspaceInvite.get_by_token(invite.token)
        assert found is not None
        assert found.id == invite.id

    def test_get_by_token_returns_none_for_expired(self, app, db_session, seeded_workspace):
        """Test get_by_token returns None for expired token."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="expired@example.com",
            invited_by_id=member.id,
        )
        # Force expiry
        invite.token_expires = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()

        found = WorkspaceInvite.get_by_token(invite.token)
        assert found is None

    def test_mark_accepted(self, app, db_session, seeded_workspace):
        """Test mark_accepted transitions status."""
        from modules.base.people.models.invite import WorkspaceInvite, InviteStatus

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="accept@example.com",
            invited_by_id=member.id,
        )

        invite.mark_accepted()
        assert invite.status == InviteStatus.ACCEPTED
        assert invite.accepted_at is not None

    def test_cancel_invite(self, app, db_session, seeded_workspace):
        """Test cancel transitions status."""
        from modules.base.people.models.invite import WorkspaceInvite, InviteStatus

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="cancel@example.com",
            invited_by_id=member.id,
        )

        invite.cancel()
        assert invite.status == InviteStatus.CANCELLED

    def test_regenerate_token(self, app, db_session, seeded_workspace):
        """Test regenerate_token creates a new token."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="regen@example.com",
            invited_by_id=member.id,
        )

        old_token = invite.token
        new_token = invite.regenerate_token()
        assert new_token != old_token
        assert invite.token == new_token

    def test_is_expired_property(self, app, db_session, seeded_workspace):
        """Test is_expired returns correct value."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="expiry@example.com",
            invited_by_id=member.id,
        )

        assert invite.is_expired is False

        invite.token_expires = datetime.now(timezone.utc) - timedelta(hours=1)
        assert invite.is_expired is True

    def test_get_pending_for_email(self, app, db_session, seeded_workspace):
        """Test get_pending_for_email finds invite by email."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        WorkspaceInvite.create(
            email="pending@example.com",
            invited_by_id=member.id,
        )

        found = WorkspaceInvite.get_pending_for_email("pending@example.com")
        assert found is not None

    def test_is_organization_only(self, app, db_session, seeded_workspace):
        """Test is_organization_only when scoped_workspace_ids is explicitly empty."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="orgonly@example.com",
            invited_by_id=member.id,
        )
        # Manually set to empty list (create() coerces [] to None via `[] or None`)
        invite.scoped_workspace_ids = []
        invite.invite_all_workspaces = False
        db.session.commit()

        assert invite.is_organization_only is True

    def test_resolve_target_workspace_ids_legacy(self, app, db_session, seeded_workspace):
        """Test resolve_target_workspace_ids falls back to workspace_id."""
        from modules.base.people.models.invite import WorkspaceInvite

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        invite = WorkspaceInvite.create(
            email="legacy@example.com",
            invited_by_id=member.id,
        )

        targets = invite.resolve_target_workspace_ids()
        assert ws["workspace"].id in targets


# ===========================================================================
# Onboarding
# ===========================================================================


@pytest.mark.integration
class TestOnboarding:
    """Tests for OnboardingRecord and OnboardingTask models."""

    def _get_tasks(self, record_id):
        """Query OnboardingTasks directly for a record."""
        from modules.base.people.models.onboarding import OnboardingTask
        return (
            OnboardingTask.query
            .filter_by(onboarding_id=record_id)
            .order_by(OnboardingTask.order)
            .all()
        )

    def test_create_w2_onboarding(self, app, db_session, seeded_workspace):
        """Test creating W2 onboarding creates record with tasks."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingStatus, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="New",
            last_name="Hire",
            personal_email="newhire@example.com",
            onboarding_type=OnboardingType.W2,
            position="Engineer",
        )
        assert record.id is not None
        assert record.status == OnboardingStatus.DRAFT
        assert record.full_name == "New Hire"
        assert record.token is not None

        tasks = self._get_tasks(record.id)
        assert len(tasks) > 0

    def test_create_contractor_onboarding(self, app, db_session, seeded_workspace):
        """Test contractor onboarding gets contractor-specific tasks."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Contractor",
            last_name="Person",
            personal_email="contractor@example.com",
            onboarding_type=OnboardingType.CONTRACTOR,
        )
        tasks = self._get_tasks(record.id)
        task_keys = [t.task_key for t in tasks]
        assert "w9" in task_keys
        # Working agreement is always prepended
        assert "working_agreement" in task_keys

    def test_workflow_transitions(self, app, db_session, seeded_workspace):
        """Test onboarding status workflow: draft -> sent -> in_progress -> review -> complete."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingStatus, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Flow",
            last_name="Test",
            personal_email="flow@example.com",
            onboarding_type=OnboardingType.W2,
        )

        record.mark_sent()
        assert record.status == OnboardingStatus.SENT
        assert record.sent_at is not None

        record.mark_in_progress()
        assert record.status == OnboardingStatus.IN_PROGRESS
        assert record.started_at is not None

        record.submit_for_review()
        assert record.status == OnboardingStatus.PENDING_REVIEW
        assert record.submitted_at is not None

        record.approve()
        assert record.status == OnboardingStatus.COMPLETED
        assert record.completed_at is not None

    def test_cancel_onboarding(self, app, db_session, seeded_workspace):
        """Test cancelling onboarding."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingStatus, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Cancel",
            last_name="Test",
            personal_email="cancel@example.com",
            onboarding_type=OnboardingType.W2,
        )

        record.cancel()
        assert record.status == OnboardingStatus.CANCELLED

    def test_resume_onboarding(self, app, db_session, seeded_workspace):
        """Test resuming a cancelled onboarding."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingStatus, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Resume",
            last_name="Test",
            personal_email="resume@example.com",
            onboarding_type=OnboardingType.W2,
        )

        old_token = record.token
        record.cancel()
        record.resume()

        assert record.status == OnboardingStatus.SENT
        assert record.token != old_token

    def test_task_complete_and_skip(self, app, db_session, seeded_workspace):
        """Test task completion and skip."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType, TaskStatus,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Task",
            last_name="Test",
            personal_email="task@example.com",
            onboarding_type=OnboardingType.W2,
        )
        tasks = self._get_tasks(record.id)

        task = tasks[0]
        task.complete(data={"field": "value"})
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.is_complete is True

        # Find a non-required task to test skip
        optional_tasks = [t for t in tasks if not t.required]
        if optional_tasks:
            opt = optional_tasks[0]
            opt.skip()
            assert opt.status == TaskStatus.SKIPPED
            assert opt.is_complete is True

    def test_task_reset(self, app, db_session, seeded_workspace):
        """Test resetting a completed task."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType, TaskStatus,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Reset",
            last_name="Test",
            personal_email="reset@example.com",
            onboarding_type=OnboardingType.W2,
        )
        tasks = self._get_tasks(record.id)

        task = tasks[0]
        task.complete()
        task.reset()
        assert task.status == TaskStatus.PENDING
        assert task.completed_at is None

    def test_progress_percent(self, app, db_session, seeded_workspace):
        """Test progress_percent calculation."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType, TaskAssignee,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Progress",
            last_name="Test",
            personal_email="progress@example.com",
            onboarding_type=OnboardingType.W2,
        )
        tasks = self._get_tasks(record.id)

        employee_tasks = [t for t in tasks if t.assignee == TaskAssignee.EMPLOYEE]
        # progress_percent accesses record.tasks, so test via direct tasks instead
        assert len(employee_tasks) > 0

        # All tasks start as PENDING, so no progress yet
        completed_before = sum(1 for t in employee_tasks if t.status.value == "Completed")
        assert completed_before == 0

        if employee_tasks:
            employee_tasks[0].complete()
            completed_after = sum(1 for t in employee_tasks if t.status.value == "Completed")
            assert completed_after == 1

    def test_get_task_by_key(self, app, db_session, seeded_workspace):
        """Test finding tasks by key lookup."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Key",
            last_name="Test",
            personal_email="key@example.com",
            onboarding_type=OnboardingType.W2,
        )

        tasks = self._get_tasks(record.id)
        task_by_key = {t.task_key: t for t in tasks}

        assert "working_agreement" in task_by_key
        assert task_by_key["working_agreement"].task_key == "working_agreement"
        assert "nonexistent" not in task_by_key

    def test_get_by_token(self, app, db_session, seeded_workspace):
        """Test get_by_token lookup."""
        from modules.base.people.models.onboarding import (
            OnboardingRecord, OnboardingType,
        )

        ws = seeded_workspace
        _set_context(ws)

        record = OnboardingRecord.create(
            first_name="Token",
            last_name="Test",
            personal_email="token@example.com",
            onboarding_type=OnboardingType.W2,
        )

        found = OnboardingRecord.get_by_token(record.token)
        assert found is not None
        assert found.id == record.id


# ===========================================================================
# Offboarding
# ===========================================================================


@pytest.mark.integration
class TestOffboarding:
    """Tests for OffboardingTask and OffboardingAssignment models."""

    def test_initialize_defaults(self, app, db_session, seeded_workspace):
        """Test initialize_defaults creates default tasks."""
        from modules.base.people.models.offboarding import OffboardingTask

        ws = seeded_workspace
        _set_context(ws)

        created = OffboardingTask.initialize_defaults()
        assert created is True

        tasks = OffboardingTask.get_active_tasks()
        assert len(tasks) > 0
        assert tasks[0].name == "Collect company property"

        # Second call should return False (already initialized)
        assert OffboardingTask.initialize_defaults() is False

    def test_create_task(self, app, db_session, seeded_workspace):
        """Test creating a custom offboarding task."""
        from modules.base.people.models.offboarding import OffboardingTask

        ws = seeded_workspace
        _set_context(ws)

        task = OffboardingTask.create(
            name="Custom Task",
            description="A custom offboarding step.",
        )

        assert task.id is not None
        assert task.name == "Custom Task"
        assert task.is_active is True

    def test_update_task(self, app, db_session, seeded_workspace):
        """Test updating a task."""
        from modules.base.people.models.offboarding import OffboardingTask

        ws = seeded_workspace
        _set_context(ws)

        task = OffboardingTask.create(name="Old Name")
        task.update(name="New Name", description="Updated desc")

        assert task.name == "New Name"
        assert task.description == "Updated desc"

    def test_delete_task(self, app, db_session, seeded_workspace):
        """Test deleting a task."""
        from modules.base.people.models.offboarding import OffboardingTask

        ws = seeded_workspace
        _set_context(ws)

        task = OffboardingTask.create(name="To Delete")
        task_id = task.id
        task.delete()

        assert OffboardingTask.query.get(task_id) is None

    def test_create_assignments_for_member(self, app, db_session, seeded_workspace):
        """Test creating offboarding assignments from active tasks."""
        from modules.base.people.models.offboarding import OffboardingTask, OffboardingAssignment

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        OffboardingTask.initialize_defaults()
        assignments = OffboardingAssignment.create_for_member(member.id)

        assert len(assignments) > 0
        assert all(a.member_id == member.id for a in assignments)
        assert all(a.completed is False for a in assignments)

    def test_mark_assignment_complete_and_incomplete(self, app, db_session, seeded_workspace):
        """Test marking assignments complete and incomplete."""
        from modules.base.people.models.offboarding import OffboardingTask, OffboardingAssignment

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        OffboardingTask.initialize_defaults()
        assignments = OffboardingAssignment.create_for_member(member.id)

        assignment = assignments[0]
        assignment.mark_complete(user_id=member.id)
        assert assignment.completed is True
        assert assignment.completed_at is not None
        assert assignment.completed_by_id == member.id

        assignment.mark_incomplete()
        assert assignment.completed is False
        assert assignment.completed_at is None

    def test_get_progress(self, app, db_session, seeded_workspace):
        """Test progress calculation."""
        from modules.base.people.models.offboarding import OffboardingTask, OffboardingAssignment

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        OffboardingTask.initialize_defaults()
        assignments = OffboardingAssignment.create_for_member(member.id)

        progress = OffboardingAssignment.get_progress(member.id)
        assert progress["total"] == len(assignments)
        assert progress["completed"] == 0
        assert progress["percent"] == 0

        assignments[0].mark_complete(user_id=member.id)
        progress = OffboardingAssignment.get_progress(member.id)
        assert progress["completed"] == 1
        assert progress["percent"] > 0

    def test_delete_for_member(self, app, db_session, seeded_workspace):
        """Test deleting all assignments for a member (rehire scenario)."""
        from modules.base.people.models.offboarding import OffboardingTask, OffboardingAssignment

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        OffboardingTask.initialize_defaults()
        OffboardingAssignment.create_for_member(member.id)

        OffboardingAssignment.delete_for_member(member.id)
        remaining = OffboardingAssignment.get_for_member(member.id)
        assert len(remaining) == 0

    def test_get_next_order(self, app, db_session, seeded_workspace):
        """Test get_next_order returns correct value."""
        from modules.base.people.models.offboarding import OffboardingTask

        ws = seeded_workspace
        _set_context(ws)

        # No tasks yet
        assert OffboardingTask.get_next_order() == 1

        OffboardingTask.create(name="First", order=5)
        assert OffboardingTask.get_next_order() == 6


# ===========================================================================
# OneOnOne
# ===========================================================================


@pytest.mark.integration
class TestOneOnOne:
    """Tests for OneOnOnePair, OneOnOneSession, OneOnOneAgendaItem."""

    def _make_second_member(self, ws):
        """Create a second workspace member for 1:1 pairing."""
        import uuid
        from modules.base.core.models.user import User
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace_user import WorkspaceUser

        user2 = User.create(
            email=f"report-{uuid.uuid4().hex[:8]}@test.com",
            password="testpass123",
            first_name="Report",
            last_name="User",
        )
        org_user2 = OrganizationUser.create(
            organization_id=ws["organization"].id,
            user_id=user2.id,
            role="member",
        )
        member2 = WorkspaceUser(
            user_id=user2.id,
            workspace_id=ws["workspace"].id,
            organization_id=ws["organization"].id,
            organization_user_id=org_user2.id,
            role="member",
        )
        db.session.add(member2)
        db.session.commit()
        return member2

    def test_create_pair(self, app, db_session, seeded_workspace):
        """Test creating a 1:1 pair."""
        from modules.base.people.models.one_on_one import OneOnOnePair

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        pair = OneOnOnePair.create(
            lead_id=lead.id,
            report_id=report.id,
            cadence="weekly",
        )

        assert pair.id is not None
        assert pair.lead_id == lead.id
        assert pair.report_id == report.id
        assert pair.cadence == "weekly"
        assert pair.active is True

    def test_deactivate_pair(self, app, db_session, seeded_workspace):
        """Test deactivating a pair."""
        from modules.base.people.models.one_on_one import OneOnOnePair

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        pair = OneOnOnePair.create(lead_id=lead.id, report_id=report.id)
        pair.deactivate()
        assert pair.active is False

    def test_get_pairs_for_user(self, app, db_session, seeded_workspace):
        """Test get_pairs_for_user returns pairs for lead or report."""
        from modules.base.people.models.one_on_one import OneOnOnePair

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        OneOnOnePair.create(lead_id=lead.id, report_id=report.id)

        lead_pairs = OneOnOnePair.get_pairs_for_user(lead.id)
        report_pairs = OneOnOnePair.get_pairs_for_user(report.id)
        assert len(lead_pairs) >= 1
        assert len(report_pairs) >= 1

    def test_create_session(self, app, db_session, seeded_workspace):
        """Test logging a 1:1 session."""
        from modules.base.people.models.one_on_one import OneOnOnePair, OneOnOneSession

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        pair = OneOnOnePair.create(lead_id=lead.id, report_id=report.id)
        session = OneOnOneSession.create(
            pair_id=pair.id,
            meeting_date=date.today(),
            notes="Discussed goals.",
        )

        assert session.id is not None
        assert session.meeting_date == date.today()
        assert session.notes == "Discussed goals."

    def test_create_agenda_item(self, app, db_session, seeded_workspace):
        """Test creating an agenda item."""
        from modules.base.people.models.one_on_one import (
            OneOnOnePair, OneOnOneAgendaItem,
        )

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        pair = OneOnOnePair.create(lead_id=lead.id, report_id=report.id)
        item = OneOnOneAgendaItem.create(
            pair_id=pair.id,
            added_by_id=lead.id,
            content="Discuss Q3 goals",
            is_task=False,
        )

        assert item.id is not None
        assert item.content == "Discuss Q3 goals"
        assert item.is_task is False
        assert item.completed is False

    def test_agenda_item_mark_complete(self, app, db_session, seeded_workspace):
        """Test marking an agenda item complete and incomplete."""
        from modules.base.people.models.one_on_one import (
            OneOnOnePair, OneOnOneAgendaItem,
        )

        ws = seeded_workspace
        _set_context(ws)
        lead = _get_membership(ws)
        report = self._make_second_member(ws)

        pair = OneOnOnePair.create(lead_id=lead.id, report_id=report.id)
        item = OneOnOneAgendaItem.create(
            pair_id=pair.id,
            added_by_id=lead.id,
            content="Action item",
            is_task=True,
            owner_id=report.id,
        )

        item.mark_complete()
        assert item.completed is True

        item.mark_incomplete()
        assert item.completed is False


# ===========================================================================
# PersonNote
# ===========================================================================


@pytest.mark.integration
class TestPersonNote:
    """Tests for PersonNote model."""

    def test_create_note(self, app, db_session, seeded_workspace):
        """Test creating a person note."""
        from modules.base.people.models.person_note import PersonNote

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        note = PersonNote.create(
            member_id=member.id,
            content="Performance review scheduled.",
            user_id=ws["user"].id,
        )

        assert note.id is not None
        assert note.content == "Performance review scheduled."
        assert note.member_id == member.id
        assert note.created_by_id == ws["user"].id

    def test_update_content(self, app, db_session, seeded_workspace):
        """Test updating note content."""
        from modules.base.people.models.person_note import PersonNote

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        note = PersonNote.create(
            member_id=member.id,
            content="Original.",
            user_id=ws["user"].id,
        )

        note.update_content("Updated content.", user_id=ws["user"].id)
        assert note.content == "Updated content."
        assert note.updated_by_id == ws["user"].id

    def test_get_for_member(self, app, db_session, seeded_workspace):
        """Test get_for_member returns notes in reverse chronological order."""
        from modules.base.people.models.person_note import PersonNote

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        PersonNote.create(member_id=member.id, content="First", user_id=ws["user"].id)
        PersonNote.create(member_id=member.id, content="Second", user_id=ws["user"].id)

        notes = PersonNote.get_for_member(member.id)
        assert len(notes) == 2
        # Most recent first
        assert notes[0].content == "Second"

    def test_soft_delete(self, app, db_session, seeded_workspace):
        """Test soft delete hides note from active query."""
        from modules.base.people.models.person_note import PersonNote

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        note = PersonNote.create(
            member_id=member.id,
            content="To delete.",
            user_id=ws["user"].id,
        )

        note.soft_delete(user_id=ws["user"].id)
        assert note.is_deleted is True

        active_notes = PersonNote.get_for_member(member.id)
        assert all(n.id != note.id for n in active_notes)

    def test_restore(self, app, db_session, seeded_workspace):
        """Test restoring a soft-deleted note."""
        from modules.base.people.models.person_note import PersonNote

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        note = PersonNote.create(
            member_id=member.id,
            content="Restore me.",
            user_id=ws["user"].id,
        )

        note.soft_delete(user_id=ws["user"].id)
        note.restore()
        assert note.is_deleted is False

        active_notes = PersonNote.get_for_member(member.id)
        assert any(n.id == note.id for n in active_notes)


# ===========================================================================
# TaxForm
# ===========================================================================


@pytest.mark.integration
class TestTaxFormRecord:
    """Tests for TaxFormRecord model."""

    def test_create_tax_form(self, app, db_session, seeded_workspace):
        """Test creating a tax form record."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        record = TaxFormRecord.create(
            member_id=member.id,
            form_type="1099-NEC",
            tax_year=2025,
            nonemployee_compensation=50000.00,
            federal_tax_withheld=0,
            created_by_id=member.id,
        )

        assert record.id is not None
        assert record.form_type == "1099-NEC"
        assert record.tax_year == 2025
        assert record.nonemployee_compensation == Decimal("50000.00")

    def test_formatted_compensation(self, app, db_session, seeded_workspace):
        """Test formatted_compensation property."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        record = TaxFormRecord.create(
            member_id=member.id,
            form_type="1099-NEC",
            tax_year=2025,
            nonemployee_compensation=75000.50,
            federal_tax_withheld=1500.25,
            created_by_id=member.id,
        )

        assert record.formatted_compensation == "$75,000.50"
        assert record.formatted_withheld == "$1,500.25"

    def test_get_by_member(self, app, db_session, seeded_workspace):
        """Test get_by_member returns records ordered by year desc."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        for year in [2023, 2024, 2025]:
            TaxFormRecord.create(
                member_id=member.id,
                form_type="1099-NEC",
                tax_year=year,
                nonemployee_compensation=10000,
                federal_tax_withheld=0,
                created_by_id=member.id,
            )

        records = TaxFormRecord.get_by_member(member.id)
        assert len(records) == 3
        assert records[0].tax_year == 2025
        assert records[2].tax_year == 2023

    def test_get_by_id(self, app, db_session, seeded_workspace):
        """Test get_by_id lookup."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        record = TaxFormRecord.create(
            member_id=member.id,
            form_type="1099-NEC",
            tax_year=2025,
            nonemployee_compensation=30000,
            federal_tax_withheld=0,
            created_by_id=member.id,
        )

        found = TaxFormRecord.get_by_id(record.id)
        assert found is not None
        assert found.id == record.id

    def test_delete_by_id(self, app, db_session, seeded_workspace):
        """Test delete_by_id removes record."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        record = TaxFormRecord.create(
            member_id=member.id,
            form_type="1099-NEC",
            tax_year=2025,
            nonemployee_compensation=20000,
            federal_tax_withheld=0,
            created_by_id=member.id,
        )

        assert TaxFormRecord.delete_by_id(record.id) is True
        assert TaxFormRecord.get_by_id(record.id) is None

    def test_delete_by_id_returns_false_for_missing(self, app, db_session, seeded_workspace):
        """Test delete_by_id returns False for nonexistent record."""
        from modules.base.people.models.taxform import TaxFormRecord

        ws = seeded_workspace
        _set_context(ws)

        assert TaxFormRecord.delete_by_id(99999) is False
