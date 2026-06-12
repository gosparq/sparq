# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module models initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from modules.base.core.models.workspace_user import WorkspaceUser, TerminationReason
from .person_note import PersonNote
from .offboarding import OffboardingAssignment, OffboardingTask
from .invite import WorkspaceInvite, InviteStatus
from .onboarding import (
    OnboardingRecord,
    OnboardingStatus,
    OnboardingTask,
    OnboardingTaskTemplate,
    OnboardingType,
    TaskAssignee,
    TaskStatus,
)

# 1:1 Tracker models
from .one_on_one import (
    OneOnOneAgendaItem,
    OneOnOnePair,
    OneOnOneSession,
)

# Hiring models (merged from hiring module)
from .hiring import (
    JobPosting,
    JobStatus,
    JobType,
    Candidate,
    CandidateSource,
    Application,
    ApplicationStatus,
    APPLICATION_STATUS_ORDER,
    Interview,
    InterviewType,
    InterviewStatus,
    InterviewRecommendation,
    ApplicationActivity,
    ActivityType,
)

__all__ = [
    # Invite models
    "WorkspaceInvite",
    "InviteStatus",
    # Team models
    "WorkspaceUser",
    "PersonNote",
    "OffboardingAssignment",
    "OffboardingTask",
    "OnboardingRecord",
    "OnboardingStatus",
    "OnboardingTask",
    "OnboardingTaskTemplate",
    "OnboardingType",
    "TaskAssignee",
    "TaskStatus",
    "TerminationReason",
    # 1:1 Tracker models
    "OneOnOnePair",
    "OneOnOneSession",
    "OneOnOneAgendaItem",
    # Hiring models
    "JobPosting",
    "JobStatus",
    "JobType",
    "Candidate",
    "CandidateSource",
    "Application",
    "ApplicationStatus",
    "APPLICATION_STATUS_ORDER",
    "Interview",
    "InterviewType",
    "InterviewStatus",
    "InterviewRecommendation",
    "ApplicationActivity",
    "ActivityType",
]
