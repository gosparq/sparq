# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Seed sample data for newly created workspaces. Creates a sample teammate
#     ("Sam Sparq") and lightweight content across key screens so new users
#     see a populated workspace on first login.
#
#     Called from PendingSignup.confirm() after provisioning (Rule 2 only —
#     brand new org creation). Failure is non-fatal — the user still gets a
#     working workspace.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Seed sample data for new workspaces.

Runs once during signup confirmation to populate a new workspace with a sample
teammate and starter content. Uses direct ORM construction (not model .create()
methods) to avoid triggering email notifications, push notifications, activity
log entries, and extra db commits during seeding. Everything is flushed in a
single transaction by the caller.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone


from system.db.database import db

logger = logging.getLogger(__name__)


def seed_sample_data(workspace_id, admin_user_id: int, admin_member_id: int) -> None:
    """Seed a sample teammate and starter content for a new workspace.

    Creates "Sam Sparq" as a sample user and populates the dashboard feed,
    weekly plan, chat, action items, calendar, projects, and notes with
    example content so new users see a populated workspace.

    Args:
        workspace_id: The workspace UUID.
        admin_user_id: The admin User.id who just signed up.
        admin_member_id: The admin WorkspaceUser.id.
    """
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus
    from modules.base.core.models.user_setting import UserSetting

    ts_hash = str(workspace_id)[:8]
    sam_user = User(
        email=f"sam-{ts_hash}@sample.sparq",
        first_name="Sam",
        last_name="Sparq",
        is_sample=True,
        is_active=False,
    )
    db.session.add(sam_user)
    db.session.flush()

    sam_member = WorkspaceUser(
        user_id=sam_user.id,
        role="member",
        status=EmployeeStatus.ACTIVE,
        position="Team Member",
    )
    db.session.add(sam_member)
    db.session.flush()

    from modules.base.presence.models.settings import TimeTrackingSettings
    TimeTrackingSettings.get()

    _seed_weekly_plan(admin_member_id)
    _seed_posts(sam_member.id)
    projects = _seed_projects(admin_member_id, sam_member.id)
    _seed_chat(sam_member.id, projects)
    _seed_tasks(admin_member_id, sam_member.id, projects)
    _seed_calendar()
    _seed_notes(sam_member.id)

    UserSetting.set(sam_user.id, "flow_status", "free")

    db.session.commit()
    logger.info("Seeded sample data for workspace %s", workspace_id)


def _seed_weekly_plan(admin_member_id: int) -> None:
    """Create 3 starter goals in the current week's plan."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

    plan = WeeklyPlan.get_or_create_current_week()
    plan.title = "Getting Started"

    goals = [
        "Explore sparQ and set up your team",
        "Invite your first real teammate",
        "Post your first team update",
    ]
    for i, text in enumerate(goals):
        goal = WeeklyPlanGoal(plan_id=plan.id, text=text, sort_order=i)
        db.session.add(goal)


def _seed_posts(sam_member_id: int) -> None:
    """Create sample update and win posts from Sam."""
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.template import UpdateTemplate

    update_tpl = UpdateTemplate.query.filter(
        UpdateTemplate.workspace_id.is_(None),
        UpdateTemplate.name == "Current",
    ).first()

    win_tpl = UpdateTemplate.query.filter(
        UpdateTemplate.workspace_id.is_(None),
        UpdateTemplate.name == "Win",
    ).first()

    announcement_tpl = UpdateTemplate.query.filter(
        UpdateTemplate.workspace_id.is_(None),
        UpdateTemplate.post_type == "board",
        UpdateTemplate.name == "Announcement",
    ).first()

    if update_tpl:
        db.session.add(UpdatePost(
            template_id=update_tpl.id,
            post_type="update",
            member_id=sam_member_id,
            payload={"body": [
                {"text": "Getting everything set up for the team"},
                {"text": "Exploring modules and configuring the workspace"},
                {"text": "Making sure everything is ready for when the crew joins"},
            ]},
        ))
        db.session.add(UpdatePost(
            template_id=update_tpl.id,
            post_type="update",
            member_id=sam_member_id,
            payload={"body": [
                {"text": "Finished setting up the project board"},
                {"text": "Added the first milestones"},
                {"text": "Next up: writing the team handbook and scheduling recurring syncs"},
            ]},
        ))

    if win_tpl:
        db.session.add(UpdatePost(
            template_id=win_tpl.id,
            post_type="win",
            member_id=sam_member_id,
            is_win=True,
            payload={"title": "Welcome to sparQ!",
                     "description": "Our new workspace is live. Time to get the "
                     "team together and start shipping."},
        ))
        db.session.add(UpdatePost(
            template_id=win_tpl.id,
            post_type="win",
            member_id=sam_member_id,
            is_win=True,
            payload={"title": "First milestone complete",
                     "description": "Workspace is configured and the first "
                     "project is underway. Onward!"},
        ))

    if announcement_tpl:
        db.session.add(UpdatePost(
            template_id=announcement_tpl.id,
            post_type="board",
            member_id=sam_member_id,
            payload={"title": "Team priorities for this week",
                     "body": "Let's align on what matters most this week."},
        ))
        db.session.add(UpdatePost(
            template_id=announcement_tpl.id,
            post_type="board",
            member_id=sam_member_id,
            payload={"title": "Ideas for improving our workflow",
                     "body": "Drop your suggestions here. No idea is too small."},
        ))


def _seed_chat(sam_member_id: int, projects: list) -> None:
    """Post messages in #general and project channels."""
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.post import UpdatePost

    general = UpdateChannel.get_by_name("general")
    if general:
        messages = [
            "Hey! I'm Sam, your sample teammate. I'm here so you can "
            "see how sparQ looks with a real team. Feel free to explore — "
            "check out the dashboard, weekly plan, and action items. "
            "When you're ready, invite your real teammates and remove me "
            "from the People page.",

            "Quick tip: you can pin important messages and use channels to "
            "organize conversations by topic.",

            "When you're ready, create a new channel for your first project. "
            "Each project gets its own channel automatically.",
        ]
        for content in messages:
            db.session.add(UpdatePost(
                payload={"content": content},
                member_id=sam_member_id,
                channel_id=general.id,
                post_type="channel",
            ))

    if projects:
        getting_started = projects[0]
        if getting_started.channel_id:
            db.session.add(UpdatePost(
                payload={"content": "This is the project channel for Getting Started. "
                         "All project updates and discussions happen here."},
                member_id=sam_member_id,
                channel_id=getting_started.channel_id,
                post_type="channel",
            ))


def _seed_tasks(admin_member_id: int, sam_member_id: int,
                       projects: list) -> None:
    """Create action items across all urgency tiers and workflow states."""
    from modules.base.tasks.models.task import Task

    getting_started_id = projects[0].id if projects else None
    q3_planning_id = projects[1].id if len(projects) > 1 else None

    now = datetime.now(timezone.utc)
    today = date.today()

    items_spec = [
        {
            "title": "Invite your first teammate",
            "urgency_tier": 1,
            "assignee_id": admin_member_id,
            "raised_by_id": sam_member_id,
            "context_note": "Head to the People page and send an invite to get your team on board.",
            "workflow_status": "to_do",
            "due_date": today + timedelta(days=2),
            "project_id": getting_started_id,
        },
        {
            "title": "Review your team's weekly plan",
            "urgency_tier": 3,
            "assignee_id": admin_member_id,
            "raised_by_id": sam_member_id,
            "context_note": "Check out this week's goals and add your own.",
            "workflow_status": "to_do",
            "project_id": getting_started_id,
        },
        {
            "title": "Complete onboarding checklist",
            "urgency_tier": 2,
            "assignee_id": sam_member_id,
            "raised_by_id": admin_member_id,
            "context_note": "Walk through the key features and set up your profile.",
            "workflow_status": "in_progress",
            "due_date": today + timedelta(days=5),
            "project_id": getting_started_id,
        },
        {
            "title": "Set up team email notifications",
            "urgency_tier": 3,
            "assignee_id": admin_member_id,
            "raised_by_id": sam_member_id,
            "context_note": "Configure email settings so your team gets notified about updates.",
            "workflow_status": "to_do",
            "due_date": today + timedelta(days=7),
        },
        {
            "title": "Decide on weekly check-in schedule",
            "urgency_tier": 2,
            "assignee_id": admin_member_id,
            "raised_by_id": sam_member_id,
            "context_note": "The team needs to agree on a recurring time for weekly syncs.",
            "workflow_status": "to_do",
            "is_blocker": True,
            "due_date": today + timedelta(days=3),
            "project_id": q3_planning_id,
        },
        {
            "title": "Create first project milestone",
            "urgency_tier": 3,
            "assignee_id": sam_member_id,
            "raised_by_id": admin_member_id,
            "context_note": "Set a target date for the first deliverable.",
            "workflow_status": "done",
            "status": "resolved",
            "resolved_at": now,
            "resolved_by_id": sam_member_id,
            "project_id": getting_started_id,
        },
        {
            "title": "Upload team logo in settings",
            "urgency_tier": 3,
            "assignee_id": admin_member_id,
            "raised_by_id": sam_member_id,
            "context_note": "Add your company logo under Settings to personalize the workspace.",
            "workflow_status": "to_do",
        },
    ]

    for spec in items_spec:
        item = Task(**spec)
        db.session.add(item)


def _seed_calendar() -> None:
    """Create upcoming events spread over the next two weeks."""
    from modules.base.updates.models.event import Event

    today = date.today()
    events = [
        {
            "title": "Team Kickoff",
            "description": "Welcome call to walk through sparQ and align on goals.",
            "scheduled_date": today + timedelta(days=1),
            "scheduled_start_time": time(10, 0),
            "scheduled_end_time": time(10, 30),
            "is_all_day": False,
            "location": "Virtual",
        },
        {
            "title": "Weekly Sync",
            "description": "Quick standup to share progress and surface blockers.",
            "scheduled_date": today + timedelta(days=3),
            "scheduled_start_time": time(9, 0),
            "scheduled_end_time": time(9, 30),
            "is_all_day": False,
            "location": "Virtual",
        },
        {
            "title": "Sprint Planning",
            "description": "Review the backlog and commit to next sprint's deliverables.",
            "scheduled_date": today + timedelta(days=7),
            "scheduled_start_time": time(14, 0),
            "scheduled_end_time": time(15, 0),
            "is_all_day": False,
            "location": "Conference Room",
        },
        {
            "title": "Team Retrospective",
            "description": "Reflect on what went well, what didn't, and what to improve.",
            "scheduled_date": today + timedelta(days=12),
            "scheduled_start_time": time(15, 0),
            "scheduled_end_time": time(15, 45),
            "is_all_day": False,
            "location": "Virtual",
        },
    ]
    for spec in events:
        db.session.add(Event(**spec))


def _seed_notes(sam_member_id: int) -> None:
    """Create team notes with onboarding content."""
    from modules.base.resources.models.note import Note

    notes = [
        {
            "member_id": sam_member_id,
            "title": "Welcome to sparQ",
            "visibility": "team",
            "is_pinned": True,
            "content": """# Welcome to sparQ

Your workspace is ready! Here's a quick guide to get started:

## Key Screens

- **Dashboard** — See what your team is working on, recent wins, and weekly stats
- **Weekly Plan** — Set goals each week and track progress together
- **Chat** — Real-time team messaging organized by channels
- **Tasks** — Track tasks with simple priority tiers (Now / Later / Whenever)
- **Calendar** — Shared team events and milestones
- **Notes** — Team and personal notes, pinned for quick access

## First Steps

1. **Explore the dashboard** — Check out the sample posts and stats
2. **Visit the Weekly Plan** — See this week's starter goals
3. **Invite your team** — Go to People and send invites
4. **Post an update** — Share what you're working on
5. **Remove Sam** — Once real teammates join, remove the sample account from People""",
        },
        {
            "member_id": sam_member_id,
            "title": "Meeting Notes: Team Kickoff",
            "visibility": "team",
            "is_pinned": False,
            "content": """# Team Kickoff — Meeting Notes

## Agenda
- Introductions and roles
- Walk through sparQ modules
- Agree on communication norms
- Set first-week goals

## Decisions
- Weekly syncs every Wednesday at 9 AM
- Use action items for anything that needs follow-up
- Post daily updates in the dashboard

## Next Steps
- Everyone: explore the workspace and set up profiles
- Admin: invite remaining team members
- Sam: draft the team handbook outline""",
        },
        {
            "member_id": sam_member_id,
            "title": "Team Norms",
            "visibility": "team",
            "is_pinned": False,
            "content": """# Team Norms

## Communication
- **Response time**: Reply to action items within 24 hours
- **Core hours**: 9 AM – 3 PM for synchronous work
- **Updates**: Post a daily update in the dashboard before end of day

## Meetings
- Keep meetings to 30 minutes unless a longer block is scheduled
- Add an agenda to the calendar event description
- Capture action items in sparQ, not in meeting notes

## Tools
- **sparQ** for all team communication, tasks, and planning
- **Calendar** for scheduling — check it before booking meetings
- **Notes** for shared documents and reference material""",
        },
    ]
    for spec in notes:
        db.session.add(Note(**spec))


def _seed_projects(admin_member_id: int, sam_member_id: int) -> list:
    """Create sample projects with dedicated chat channels."""
    from modules.base.projects.models.project import Project
    from modules.base.updates.models.channel import UpdateChannel

    projects_spec = [
        {
            "name": "Getting Started",
            "channel_name": "getting-started",
            "description": "Set up your workspace, invite your team, "
                          "and hit your first milestones.",
            "status": Project.STATUS_CURRENT,
            "color": "#3b82f6",
            "owner_id": sam_member_id,
            "created_by_id": sam_member_id,
        },
        {
            "name": "Q3 Planning",
            "channel_name": "q3-planning",
            "description": "Map out goals, timelines, and deliverables "
                          "for the next quarter.",
            "status": Project.STATUS_UPCOMING,
            "color": "#8b5cf6",
            "owner_id": admin_member_id,
            "created_by_id": admin_member_id,
        },
        {
            "name": "Team Handbook",
            "channel_name": "team-handbook",
            "description": "Document team processes, norms, and onboarding guides.",
            "status": Project.STATUS_ON_HOLD,
            "color": "#f59e0b",
            "owner_id": sam_member_id,
            "created_by_id": sam_member_id,
        },
    ]

    created_projects = []
    for spec in projects_spec:
        channel_name = spec.pop("channel_name")
        channel = UpdateChannel(
            name=channel_name,
            description=f"Project channel for {spec['name']}",
            created_by_id=spec["created_by_id"],
            is_private=False,
        )
        db.session.add(channel)
        db.session.flush()

        project = Project(channel_id=channel.id, **spec)
        db.session.add(project)
        db.session.flush()

        created_projects.append(project)

    return created_projects


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def remove_sample_data(workspace_id) -> bool:
    """Remove all sample data from a workspace.

    Finds the sample user's WorkspaceUser, then deletes all records created
    by that member in dependency order. Called when an admin removes Sam
    from the People page.

    Args:
        workspace_id: The workspace UUID to clean up.

    Returns:
        True if sample data was found and removed, False otherwise.
    """
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user_setting import UserSetting
    from modules.base.tasks.models.task import Task, task_watcher
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.event import Event
    from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal
    from modules.base.resources.models.note import Note
    from modules.base.projects.models.project import Project

    sam_member = (
        WorkspaceUser.query
        .join(User, WorkspaceUser.user_id == User.id)
        .filter(
            WorkspaceUser.workspace_id == workspace_id,
            User.is_sample.is_(True),
        )
        .first()
    )
    if not sam_member:
        return False

    sam_user_id = sam_member.user_id
    sam_member_id = sam_member.id

    # Action item watchers for items involving Sam
    sam_items = Task.query.filter(
        Task.workspace_id == workspace_id,
        db.or_(
            Task.raised_by_id == sam_member_id,
            Task.assignee_id == sam_member_id,
        ),
    ).all()
    sam_item_ids = [item.id for item in sam_items]

    if sam_item_ids:
        db.session.execute(
            task_watcher.delete().where(
                task_watcher.c.task_id.in_(sam_item_ids)
            )
        )
        Task.query.filter(Task.id.in_(sam_item_ids)).delete(
            synchronize_session=False
        )

    # Posts authored by Sam
    UpdatePost.query.filter(
        UpdatePost.workspace_id == workspace_id,
        UpdatePost.member_id == sam_member_id,
    ).delete(synchronize_session=False)

    # Notes authored by Sam
    Note.query.filter(
        Note.workspace_id == workspace_id,
        Note.member_id == sam_member_id,
    ).delete(synchronize_session=False)

    # Projects owned/created by Sam (and their channels)
    sam_projects = Project.query.filter(
        Project.workspace_id == workspace_id,
        db.or_(
            Project.owner_id == sam_member_id,
            Project.created_by_id == sam_member_id,
        ),
    ).all()
    project_channel_ids = [p.channel_id for p in sam_projects if p.channel_id]

    # Also remove admin-owned projects that are seed data
    admin_seed_projects = Project.query.filter(
        Project.workspace_id == workspace_id,
        Project.name.in_(["Getting Started", "Q3 Planning", "Team Handbook"]),
    ).all()
    for p in admin_seed_projects:
        if p.channel_id and p.channel_id not in project_channel_ids:
            project_channel_ids.append(p.channel_id)
        if p not in sam_projects:
            sam_projects.append(p)

    for project in sam_projects:
        db.session.delete(project)
    db.session.flush()

    if project_channel_ids:
        # Clean up posts in project channels before deleting channels
        UpdatePost.query.filter(
            UpdatePost.channel_id.in_(project_channel_ids),
        ).delete(synchronize_session=False)

        UpdateChannel.query.filter(
            UpdateChannel.id.in_(project_channel_ids),
        ).delete(synchronize_session=False)

    # Seed events (identified by known titles)
    _SEED_EVENT_TITLES = {"Team Kickoff", "Weekly Sync", "Sprint Planning",
                          "Team Retrospective"}
    Event.query.filter(
        Event.workspace_id == workspace_id,
        Event.title.in_(_SEED_EVENT_TITLES),
    ).delete(synchronize_session=False)

    # Weekly plan + goals for the "Getting Started" plan
    getting_started_plan = WeeklyPlan.query.filter(
        WeeklyPlan.workspace_id == workspace_id,
        WeeklyPlan.title == "Getting Started",
    ).first()
    if getting_started_plan:
        WeeklyPlanGoal.query.filter_by(plan_id=getting_started_plan.id).delete(
            synchronize_session=False
        )
        db.session.delete(getting_started_plan)

    # User settings for Sam
    UserSetting.query.filter(
        UserSetting.workspace_id == workspace_id,
        UserSetting.user_id == sam_user_id,
    ).delete(synchronize_session=False)

    # Hard delete WorkspaceUser and User (sample user, not a real person)
    db.session.delete(sam_member)
    db.session.flush()

    sam_user = User.query.get(sam_user_id)
    if sam_user:
        db.session.delete(sam_user)

    db.session.commit()
    logger.info("Removed sample data for workspace %s", workspace_id)
    return True
