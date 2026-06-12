# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Weekly Plans controller — detail views and goal management for weekly plans."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from system.i18n.translation import translate as _

from system.device.template import render_device_template

from . import blueprint


@blueprint.route("/plans")
@login_required
def plans_index():
    """Weekly plans landing — redirects to current week's plan."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan

    plan = WeeklyPlan.get_or_create_current_week()
    return redirect(url_for("tasks_bp.plan_detail", year=plan.year, week=plan.week_number))


@blueprint.route("/plans/history")
@login_required
def plans_history():
    """List past weekly plans."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan

    plans = WeeklyPlan.get_recent(limit=12)

    return render_device_template(
        "updates/desktop/weekly_plan/index.html",
        active_page="plans",
        module_home="tasks_bp.board",
        plans=plans,
    )


@blueprint.route("/plans/<int:year>/<int:week>")
@login_required
def plan_detail(year, week):
    """Detail view for a specific weekly plan with linked activity."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan
    from modules.base.updates.models.post import UpdatePost
    # SyncBlocker table dropped — blocker data now lives in Task
    from modules.base.updates.models.area import UpdateArea

    plan = WeeklyPlan.get_by_week(year, week)
    if not plan:
        flash(_("No plan found for that week."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    week_posts = UpdatePost.get_for_date_range(plan.start_date, plan.end_date, post_types=["update", "win"])
    # SyncBlocker table dropped — use Task open blockers instead
    week_blockers = []
    try:
        from modules.base.tasks.models.task import Task
        if plan.is_current_week:
            week_blockers = Task.get_open_blockers()
        else:
            week_blockers = [a for a in Task.get_for_date_range(plan.start_date, plan.end_date) if a.is_blocker]
    except Exception:
        pass

    week_actions = []
    try:
        from modules.base.tasks.models.task import Task
        all_actions = Task.get_for_date_range(plan.start_date, plan.end_date)
        week_actions = [a for a in all_actions if not a.is_system_raised]
    except Exception:
        pass

    areas = UpdateArea.get_all()

    # Week in Review for this week
    week_review = None
    try:
        from modules.base.updates.models.week_review import UpdateWeekReview
        week_review = UpdateWeekReview.get_for_week_start(plan.start_date)
    except Exception:
        pass

    return render_device_template(
        "updates/desktop/weekly_plan/detail.html",
        active_page="plans",
        module_home="tasks_bp.board",
        plan=plan,
        goals=plan.goal_list(),
        week_posts=week_posts,
        week_blockers=week_blockers,
        week_actions=week_actions,
        areas=areas,
        week_review=week_review,
    )


@blueprint.route("/plans/<int:year>/<int:week>/edit")
@login_required
def plan_edit(year, week):
    """Edit page for a weekly plan — title and goals CRUD."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("tasks_bp.plan_detail", year=year, week=week))

    from modules.base.updates.models.weekly_plan import WeeklyPlan

    plan = WeeklyPlan.get_by_week(year, week)
    if not plan:
        flash(_("No plan found for that week."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    return render_device_template(
        "updates/desktop/weekly_plan/edit.html",
        active_page="plans",
        module_home="tasks_bp.board",
        plan=plan,
        goals=plan.goal_list(),
    )


@blueprint.route("/plans/<int:plan_id>/update", methods=["POST"])
@login_required
def plan_update(plan_id):
    """Update a weekly plan's title (admin only)."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    from modules.base.updates.models.weekly_plan import WeeklyPlan

    plan = WeeklyPlan.get_by_id(plan_id)
    if not plan:
        flash(_("Plan not found."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    title = request.form.get("title", "")

    plan.update(title=title)
    flash(_("Plan saved."), "success")
    return redirect(url_for("tasks_bp.plan_detail", year=plan.year, week=plan.week_number))


def _render_goals_partial(plan):
    """Render the goals HTMX partial for a plan."""
    return render_template(
        "updates/desktop/weekly_plan/_goals.html",
        plan=plan,
        goals=plan.goal_list(),
    )


@blueprint.route("/plans/<int:plan_id>/goals/add", methods=["POST"])
@login_required
def plan_goal_add(plan_id):
    """Add a goal to a weekly plan. Returns HTMX partial or redirects."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

    plan = WeeklyPlan.get_by_id(plan_id)
    if not plan:
        if request.headers.get("HX-Request"):
            return "", 404
        flash(_("Plan not found."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    text = request.form.get("text", "").strip()
    if text and plan.goals_total_count < 6:
        WeeklyPlanGoal.add_to_plan(plan_id=plan.id, text=text)

    if request.headers.get("HX-Request"):
        return _render_goals_partial(plan)

    return redirect(url_for("tasks_bp.plan_edit", year=plan.year, week=plan.week_number))


@blueprint.route("/plans/<int:plan_id>/goals/<int:goal_id>/toggle", methods=["POST"])
@login_required
def plan_goal_toggle(plan_id, goal_id):
    """Toggle a goal's completion status. Returns HTMX partial or JSON."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

    plan = WeeklyPlan.get_by_id(plan_id)
    if not plan:
        return {"error": "Plan not found"}, 404

    goal = WeeklyPlanGoal.query.get(goal_id)
    if not goal or goal.plan_id != plan.id:
        return {"error": "Goal not found"}, 404

    goal.toggle_complete()

    # Auto-create a win post when a goal is completed
    if goal.is_complete:
        _create_win_from_goal(goal)

    if request.headers.get("HX-Request"):
        return render_template(
            "updates/desktop/weekly_plan/_goal_item.html",
            plan=plan,
            goal=goal,
        )

    return {"ok": True, "is_complete": goal.is_complete}


@blueprint.route("/plans/<int:plan_id>/goals/<int:goal_id>/delete", methods=["POST"])
@login_required
def plan_goal_delete(plan_id, goal_id):
    """Delete a goal from a weekly plan. Returns HTMX partial or redirects."""
    from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

    plan = WeeklyPlan.get_by_id(plan_id)
    if not plan:
        if request.headers.get("HX-Request"):
            return "", 404
        flash(_("Plan not found."), "error")
        return redirect(url_for("tasks_bp.plans_index"))

    goal = WeeklyPlanGoal.query.get(goal_id)
    if goal and goal.plan_id == plan.id:
        goal.delete()

    if request.headers.get("HX-Request"):
        return _render_goals_partial(plan)

    return redirect(url_for("tasks_bp.plan_edit", year=plan.year, week=plan.week_number))


def _create_win_from_goal(goal):
    """Create a win post when a goal is completed."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.template import UpdateTemplate

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        return

    # Find the built-in "Win" template
    win_templates = UpdateTemplate.get_for_workspace(post_type="win")
    if not win_templates:
        return
    win_template = win_templates[0]

    UpdatePost.create(
        template=win_template,
        member_id=member.id,
        payload={"title": goal.text, "description": "Goal completed"},
    )
