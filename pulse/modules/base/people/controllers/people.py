# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module controllers for employee management.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import logging

from flask import flash
from flask import g
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user
from flask_login import login_required

from sqlalchemy.orm import joinedload, selectinload

from system.device.template import render_device_template
from system.i18n.translation import translate as _

from modules.base.core.models.user import User
from modules.base.core.models.workspace_user import (
    WorkspaceUser,
    EmployeeStatus,
    EmployeeType,
    SalaryType,
    TerminationReason,
)
from ..decorators import admin_required
from ..models.person_note import PersonNote
from ..models.offboarding import OffboardingAssignment, OffboardingTask
from system.db.database import db

from . import blueprint

logger = logging.getLogger(__name__)


@blueprint.route("/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def team_home() -> str:
    """Team module landing - redirects to Team page"""
    return redirect(url_for("people_bp.people"))


@blueprint.route("/people/me")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def my_profile() -> str:
    """Redirect to current user's employee profile."""
    member = WorkspaceUser.scoped().filter_by(user_id=current_user.id).first()
    if member:
        return redirect(url_for("people_bp.person_detail", employee_id=member.id))
    flash(_("No employee record found"), "warning")
    return redirect(url_for("people_bp.people"))


@blueprint.route("/people/organization/")  # type: ignore[misc]
@blueprint.route("/people/organization")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def people_organization() -> str:
    """Organization directory — every person across all workspaces in the org.

    Phase 6 §5: inline organization view of the People module. Shows one
    entry per user, ordered by name, with the list of workspaces they belong
    to. Org-only members (§3.5) and cross-workspace members all surface here.
    """
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace

    if not getattr(g, "organization_id", None):
        flash(_("No active organization context."), "error")
        return redirect(url_for("dashboard_bp.index"))  # type: ignore[no-any-return]

    search = request.args.get("search", "").strip()

    # Every active OrganizationUser with the joined User and the user's
    # non-archived workspace memberships.
    org_members = OrganizationUser.list_for_organization(
        g.organization_id, active_only=True
    )

    # Build a display record per member.
    directory = []
    all_workspaces = {
        t.id: t for t in Workspace.query.filter_by(organization_id=g.organization_id).all()
    }
    for om in org_members:
        user = om.user
        if user is None or not user.is_active:
            continue
        if search:
            needle = search.lower()
            haystack = f"{user.first_name or ''} {user.last_name or ''} {user.email or ''}".lower()
            if needle not in haystack:
                continue
        memberships = [
            tu for tu in om.workspace_users.filter(WorkspaceUser.deleted_at.is_(None)).all()
        ]
        workspace_entries = [
            {
                "name": all_workspaces[tu.workspace_id].name,
                "archived": all_workspaces[tu.workspace_id].deleted_at is not None,
            }
            for tu in memberships
            if tu.workspace_id in all_workspaces
        ]
        directory.append({
            "user": user,
            "role": om.role,
            "workspaces": workspace_entries,
        })
    directory.sort(key=lambda r: ((r["user"].first_name or ""), (r["user"].last_name or "")))

    return render_device_template(  # type: ignore[no-any-return]
        "people/desktop/people/organization.html",
        active_page="people",
        directory=directory,
        search=search,
        workspace_path=url_for("people_bp.people"),
        organization_path=url_for("people_bp.people_organization"),
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def people() -> str:
    """Employees list page"""
    from ..queries.directory import get_directory_members, get_directory_stats

    # Redirect org-only members (no WorkspaceUser) to the organization view.
    if (
        current_user.is_authenticated
        and getattr(g, "workspace_id", None) is None
        and getattr(g, "organization_id", None) is not None
    ):
        return redirect(url_for("people_bp.people_organization"))  # type: ignore[no-any-return]

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "")

    users = get_directory_members(
        g.organization_id, g.workspace_id,
        search=search, status_filter=status_filter,
    )
    stats = get_directory_stats(g.organization_id, g.workspace_id)

    # Pending invites (admin only)
    pending_invites = []
    pending_invite_count = 0
    if current_user.is_admin:
        from ..models.invite import WorkspaceInvite
        pending_invites = WorkspaceInvite.get_pending_all()
        pending_invite_count = len(pending_invites)

    # Organization-admin context for the invite modal.
    is_organization_admin = False
    organization_workspaces = []
    if current_user.is_admin and getattr(g, "organization_id", None):
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace

        org_membership = OrganizationUser.get_for_user(current_user.id, g.organization_id)
        if org_membership and org_membership.is_organization_admin:
            is_organization_admin = True
            organization_workspaces = (
                Workspace.query
                .filter_by(organization_id=g.organization_id)
                .order_by(Workspace.name)
                .all()
            )

    # Existing org members not yet in this workspace (for the "Add Members" modal).
    eligible_members: list = []
    if current_user.is_admin and getattr(g, "workspace_id", None):
        eligible_members = WorkspaceUser.eligible_members(g.organization_id, g.workspace_id)

    return render_device_template(  # type: ignore[no-any-return]
        "people/desktop/people/index.html",
        active_page="people",
        users=users,
        search=search,
        status_filter=status_filter,
        total_count=stats.total_count,
        active_count=stats.active_count,
        on_leave_count=stats.on_leave_count,
        terminated_count=stats.terminated_count,
        contractor_count=stats.contractor_count,
        pending_invites=pending_invites,
        pending_invite_count=pending_invite_count,
        is_organization_admin=is_organization_admin,
        organization_workspaces=organization_workspaces,
        eligible_members=eligible_members,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people/members/add", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def add_members() -> ResponseReturnValue:
    """Add existing organization members to the current workspace.

    Accepts a form field ``user_ids`` (repeated) of existing org members and
    adds each to the current workspace as a ``member``. Idempotent and
    admin-only.
    """
    user_ids: list[int] = []
    for raw_id in request.form.getlist("user_ids"):
        try:
            user_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not user_ids:
        flash(_("Select at least one member to add."), "warning")
        return redirect(url_for("people_bp.people"))

    added = WorkspaceUser.add_existing_members(user_ids)
    if added:
        flash(_("Added {n} member(s) to this workspace.").format(n=len(added)), "success")
    else:
        flash(_("No new members were added."), "info")
    return redirect(url_for("people_bp.people"))


@blueprint.route("/people/profile/<int:member_id>")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def person_profile(member_id: int) -> str:
    """Public-facing profile page for a member."""
    from system.module.registry import module_enabled
    from modules.base.core.models.user_setting import UserSetting

    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=member_id).first_or_404()

    flow_status = UserSetting.get(member.user_id, "flow_status", default="free")

    # Get recent posts by this member (Connect module)
    recent_posts = []
    if module_enabled("Updates"):
        from modules.base.updates.models.post import UpdatePost
        recent_posts = (
            UpdatePost.scoped()
            .filter(
                UpdatePost.member_id == member_id,
                UpdatePost.post_type.in_(["update", "win"]),
            )
            .order_by(UpdatePost.created_at.desc())
            .limit(5)
            .all()
        )

    return render_device_template(  # type: ignore[no-any-return]
        "people/desktop/people/profile.html",
        active_page="people",
        employee=member,
        flow_status=flow_status,
        recent_posts=recent_posts,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people/new", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def new_person() -> str:
    """Show new employee form"""
    from flask import current_app

    # Get all employees as potential managers
    potential_managers = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).join(User, WorkspaceUser.user_id == User.id).order_by(User.first_name).all()

    # Collect form extensions from plugins via hooks
    form_extensions = []
    if hasattr(current_app, "module_loader"):
        pm = current_app.module_loader.pm
        results = pm.hook.modify_new_employee_form()
        for result in results:
            if result:
                form_extensions.extend(result)

    return render_template(  # type: ignore[no-any-return]
        "people/desktop/people/form.html",
        title="New Person",
        employee=None,
        employee_types=EmployeeType,
        potential_managers=potential_managers,
        form_extensions=form_extensions,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def create_person() -> str:
    """Create a new employee"""
    from flask import current_app

    try:
        # Validate required fields
        email = request.form.get("email")
        if not email:
            flash(_("Email is required"), "error")
            return redirect(url_for("people_bp.new_person"))

        # Check if user already exists
        if User.query.filter_by(email=email).first():
            flash(_("An account with this email already exists"), "error")
            return redirect(url_for("people_bp.new_person"))

        # Create user
        user = User.create(
            email=email,
            password=request.form.get("password"),
            first_name=request.form.get("first_name", ""),
            last_name=request.form.get("last_name", ""),
        )

        # Set personal fields on the User (person-level data)
        user.phone = request.form.get("phone", "")
        user.personal_phone = request.form.get("phone", "")
        user.address = request.form.get("address", "")
        user.address_2 = request.form.get("address_2", "")
        user.city = request.form.get("city", "")
        user.state = request.form.get("state", "")
        user.zip_code = request.form.get("zip_code", "")
        user.emergency_contact_name = request.form.get("emergency_contact_name", "")
        user.emergency_contact_phone = request.form.get("emergency_contact_phone", "")
        user.emergency_contact_relationship = request.form.get("emergency_contact_relationship", "")

        # Create workspace membership (employment data)
        is_admin = bool(request.form.get("is_admin", False))
        member = WorkspaceUser(
            user_id=user.id,
            role="admin" if is_admin else "member",
            department=request.form.get("department", ""),
            position=request.form.get("position", ""),
            type=EmployeeType[request.form.get("type", "FULL_TIME")],
            status=EmployeeStatus.ACTIVE,
            phone=request.form.get("phone", ""),
        )

        # Set permission areas (only for non-admin — admins have all access)
        if not is_admin:
            permission_areas = []
            for form_field, area in [("perm_hr", "hr"), ("perm_finance", "finance"), ("perm_operations", "operations")]:
                if request.form.get(form_field) == "on":
                    permission_areas.append(area)
            member.set_permissions(permission_areas)

        # Add manager if selected
        manager_id = request.form.get("manager_id")
        if manager_id:
            member.manager_id = int(manager_id)

        # Handle start date
        start_date = request.form.get("start_date")
        if start_date:
            from datetime import datetime
            member.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        # Handle salary
        salary = request.form.get("salary")
        if salary:
            member.salary = float(salary)

        # Handle salary type
        salary_type = request.form.get("salary_type")
        if salary_type:
            member.salary_type = SalaryType[salary_type]

        # Handle personal info (stored on User)
        birthday = request.form.get("birthday")
        if birthday:
            from datetime import datetime
            user.birthday = datetime.strptime(birthday, "%Y-%m-%d").date()

        gender = request.form.get("gender")
        if gender:
            from modules.base.core.models.workspace_user import Gender
            user.gender = Gender[gender].value

        # Handle clock PIN
        clock_pin = request.form.get("clock_pin", "").strip()
        if clock_pin:
            if len(clock_pin) != 4 or not clock_pin.isdigit():
                flash(_("PIN must be exactly 4 digits"), "error")
                return redirect(url_for("people_bp.new_person"))
            member.clock_pin = clock_pin
        else:
            member.clock_pin = None

        db.session.add(member)
        db.session.commit()

        # Call plugin hooks to process additional form data
        if hasattr(current_app, "module_loader"):
            pm = current_app.module_loader.pm
            pm.hook.process_new_employee(form_data=request.form, employee=member)

        flash(_("Employee created successfully"), "success")
        return redirect(url_for("people_bp.people"))

    except Exception as e:
        db.session.rollback()
        flash(_("Error creating employee: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.new_person"))


@blueprint.route("/people/<int:employee_id>/edit", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def edit_person(employee_id: int) -> str:
    """Show edit employee form"""
    from flask import current_app

    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()

    potential_managers = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).join(User, WorkspaceUser.user_id == User.id).order_by(User.first_name).all()

    # Get admin count if the employee is an admin
    admin_count = 0
    if member.user.is_admin:
        admin_count = WorkspaceUser.scoped().filter_by(role="admin").count()

    # Collect form extensions from plugins via hooks
    form_extensions = []
    if hasattr(current_app, "module_loader"):
        pm = current_app.module_loader.pm
        results = pm.hook.modify_edit_employee_form(employee=member)
        for result in results:
            if result:
                form_extensions.extend(result)

    return render_template(  # type: ignore[no-any-return]
        "people/desktop/people/form.html",
        title="Edit Person",
        employee=member,
        employee_types=EmployeeType,
        potential_managers=potential_managers,
        admin_count=admin_count,
        form_extensions=form_extensions,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people/<int:employee_id>", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def update_person(employee_id: int) -> str:
    """Update an employee"""
    from flask import current_app

    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
        user = member.user

        # Role and permission changes are handled by update_user_permissions —
        # do not mutate member.role or member.permissions here.

        # Update user fields
        user.first_name = request.form.get("first_name", user.first_name)
        user.last_name = request.form.get("last_name", user.last_name)
        user.email = request.form.get("email", user.email)

        # Update password if provided
        password = request.form.get("password", "").strip()
        if password:
            user.password = password

        # Update workspace membership fields
        member.department = request.form.get("department", member.department)
        member.position = request.form.get("position", member.position)
        member.phone = request.form.get("phone", member.phone)

        # Update personal fields on User
        user.address = request.form.get("address", user.address)
        user.address_2 = request.form.get("address_2", user.address_2)
        user.city = request.form.get("city", user.city)
        user.state = request.form.get("state", user.state)
        user.zip_code = request.form.get("zip_code", user.zip_code)

        # Handle manager
        manager_id = request.form.get("manager_id")
        member.manager_id = int(manager_id) if manager_id else None

        # Handle employee type
        emp_type = request.form.get("type")
        if emp_type:
            member.type = EmployeeType[emp_type]

        # Handle start date
        start_date = request.form.get("start_date")
        if start_date:
            from datetime import datetime
            member.start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

        # Handle salary
        salary = request.form.get("salary")
        member.salary = float(salary) if salary else None

        # Handle salary type
        salary_type = request.form.get("salary_type")
        if salary_type:
            member.salary_type = SalaryType[salary_type]

        member.pulse_exempt = "pulse_exempt" in request.form

        # Handle personal info (stored on User)
        birthday = request.form.get("birthday")
        if birthday:
            from datetime import datetime
            user.birthday = datetime.strptime(birthday, "%Y-%m-%d").date()

        gender = request.form.get("gender")
        if gender:
            from modules.base.core.models.workspace_user import Gender
            user.gender = Gender[gender].value
        else:
            user.gender = None

        # Handle emergency contact (stored on User)
        user.emergency_contact_name = request.form.get("emergency_contact_name", user.emergency_contact_name)
        user.emergency_contact_phone = request.form.get("emergency_contact_phone", user.emergency_contact_phone)
        user.emergency_contact_relationship = request.form.get("emergency_contact_relationship", user.emergency_contact_relationship)

        # Handle clock PIN
        clock_pin = request.form.get("clock_pin", "").strip()
        if clock_pin:
            if len(clock_pin) != 4 or not clock_pin.isdigit():
                flash(_("PIN must be exactly 4 digits"), "error")
                return redirect(url_for("people_bp.edit_person", employee_id=employee_id))
            member.clock_pin = clock_pin
        else:
            member.clock_pin = None

        db.session.commit()

        # Call plugin hooks to process additional form data
        if hasattr(current_app, "module_loader"):
            pm = current_app.module_loader.pm
            pm.hook.process_employee_update(form_data=request.form, employee=member)

        flash(_("Employee updated successfully"), "success")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    except Exception as e:
        db.session.rollback()
        flash(_("Error updating employee: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.edit_person", employee_id=employee_id))


@blueprint.route("/people/<int:employee_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def delete_person(employee_id: int) -> str:
    """Delete an employee"""
    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
        user = member.user

        db.session.delete(member)
        db.session.delete(user)
        db.session.commit()

        flash(_("Employee deleted successfully"), "success")
        return redirect(url_for("people_bp.people"))

    except Exception as e:
        db.session.rollback()
        flash(_("Error deleting employee: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.people"))


@blueprint.route("/people/<int:employee_id>/delete-modal", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def delete_modal(employee_id: int) -> str:
    """Show delete confirmation modal with hard delete warning"""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    return render_template("people/desktop/people/delete-modal.html", employee=member)


@blueprint.route("/people/<int:employee_id>/remove-modal", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def remove_modal(employee_id: int) -> str:
    """Show remove from workspace confirmation modal."""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    return render_template("people/desktop/people/remove-modal.html", employee=member)


@blueprint.route("/people/<int:employee_id>/remove", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def remove_person(employee_id: int) -> str:
    """Remove a member from the workspace (soft delete, preserves user account)."""
    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
        name = f"{member.user.first_name} {member.user.last_name}"

        member.remove_from_workspace()

        flash(
            _("%(name)s has been removed from the workspace.") % {"name": name},
            "success",
        )
        return redirect(url_for("people_bp.people"))

    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))
    except Exception as e:
        db.session.rollback()
        flash(
            _("Error removing member: %(error)s") % {"error": str(e)},
            "error",
        )
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))


@blueprint.route("/people/<int:employee_id>/terminate-modal", methods=["GET"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def terminate_modal(employee_id: int) -> str:
    """Show terminate employee modal"""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()
    return render_template(
        "people/desktop/people/terminate-modal.html",
        employee=member,
        termination_reasons=TerminationReason,
    )


@blueprint.route("/people/<int:employee_id>/terminate", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def terminate_person(employee_id: int) -> str:
    """Terminate an employee"""
    from datetime import datetime

    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()

        # Get termination details
        reason_str = request.form.get("termination_reason", "OTHER")
        termination_date_str = request.form.get("termination_date")

        # Parse reason
        try:
            reason = TerminationReason[reason_str]
        except KeyError:
            reason = TerminationReason.OTHER

        # Parse date
        termination_date = None
        if termination_date_str:
            termination_date = datetime.strptime(termination_date_str, "%Y-%m-%d").date()

        # Terminate the employee
        member.terminate(reason=reason, termination_date=termination_date)

        # Initialize default offboarding tasks if none exist
        OffboardingTask.initialize_defaults()

        # Create offboarding assignments
        OffboardingAssignment.create_for_member(member.id)

        flash(_("%(name)s has been terminated.") % {"name": f"{member.user.first_name} {member.user.last_name}"}, "success")
        return redirect(url_for("people_bp.person_offboarding", employee_id=employee_id))

    except Exception as e:
        db.session.rollback()
        flash(_("Error terminating employee: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))


@blueprint.route("/people/<int:employee_id>/rehire", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def rehire_person(employee_id: int) -> str:
    """Rehire a terminated employee"""
    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()

        if member.status != EmployeeStatus.TERMINATED:
            flash(_("Only terminated employees can be rehired."), "error")
            return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

        # Rehire the employee
        member.rehire()

        # Clear old offboarding assignments
        OffboardingAssignment.delete_for_member(member.id)

        flash(_("%(name)s has been rehired.") % {"name": f"{member.user.first_name} {member.user.last_name}"}, "success")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    except Exception as e:
        db.session.rollback()
        flash(_("Error rehiring employee: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))


@blueprint.route("/people/<int:employee_id>/offboarding")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def person_offboarding(employee_id: int) -> str:
    """View offboarding checklist for a terminated employee"""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()

    if member.status != EmployeeStatus.TERMINATED:
        flash(_("Offboarding is only available for terminated employees."), "error")
        return redirect(url_for("people_bp.person_detail", employee_id=employee_id))

    assignments = OffboardingAssignment.get_for_member(employee_id)
    progress = OffboardingAssignment.get_progress(employee_id)

    return render_template(
        "people/desktop/people/offboarding.html",
        employee=member,
        assignments=assignments,
        progress=progress,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people/<int:employee_id>/offboarding/<int:assignment_id>/toggle", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def toggle_offboarding_task(employee_id: int, assignment_id: int) -> str:
    """Toggle an offboarding task completion status"""
    assignment = OffboardingAssignment.scoped().get_or_404(assignment_id)

    if assignment.member_id != employee_id:
        return jsonify({"error": "Invalid assignment"}), 404

    if assignment.completed:
        assignment.mark_incomplete()
    else:
        assignment.mark_complete(current_user.id)

    # Return updated checklist partial
    assignments = OffboardingAssignment.get_for_member(employee_id)
    progress = OffboardingAssignment.get_progress(employee_id)

    return render_template(
        "people/desktop/people/_offboarding_checklist.html",
        employee_id=employee_id,
        assignments=assignments,
        progress=progress,
    )


# -----------------------------------------------------------------------------
# Offboarding List & Task Template Management
# -----------------------------------------------------------------------------


@blueprint.route("/offboarding")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def offboarding_list() -> str:
    """List all employees currently in offboarding (terminated)"""
    # Get all terminated employees
    terminated_employees = (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter(WorkspaceUser.status == EmployeeStatus.TERMINATED)
        .join(User, WorkspaceUser.user_id == User.id)
        .order_by(WorkspaceUser.termination_date.desc())
        .all()
    )

    # Calculate progress for each employee
    employees_with_progress = []
    for emp in terminated_employees:
        progress = OffboardingAssignment.get_progress(emp.id)
        employees_with_progress.append({
            "member": emp,
            "progress": progress,
        })

    return render_template(
        "people/desktop/offboarding/index.html",
        employees=employees_with_progress,
        active_page="offboarding",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/offboarding/task/new", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def create_offboarding_task() -> str:
    """Create a new offboarding task template."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        order = int(request.form.get("order", 0))

        if not name:
            flash(_("Task name is required."), "error")
        else:
            try:
                OffboardingTask.create(name=name, description=description, order=order)
                flash(_("Offboarding task created."), "success")
                return redirect(url_for("people_bp.team_settings", tab="offboarding"))
            except Exception as e:
                db.session.rollback()
                flash(_("Error creating task: %(error)s") % {"error": str(e)}, "error")

    next_order = OffboardingTask.get_next_order()

    return render_template(
        "people/desktop/offboarding/task_form.html",
        task=None,
        next_order=next_order,
        active_page="settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/offboarding/task/<int:task_id>/edit", methods=["GET", "POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def update_offboarding_task(task_id: int) -> str:
    """Edit an existing offboarding task template."""
    task = OffboardingTask.scoped().get_or_404(task_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        is_active = request.form.get("is_active") == "on"
        order = int(request.form.get("order", 0))

        if not name:
            flash(_("Task name is required."), "error")
        else:
            try:
                task.update(name=name, description=description, is_active=is_active, order=order)
                flash(_("Offboarding task updated."), "success")
                return redirect(url_for("people_bp.team_settings", tab="offboarding"))
            except Exception as e:
                db.session.rollback()
                flash(_("Error updating task: %(error)s") % {"error": str(e)}, "error")

    return render_template(
        "people/desktop/offboarding/task_form.html",
        task=task,
        active_page="settings",
        module_home="dashboard_bp.index",
    )


@blueprint.route("/settings/offboarding/task/<int:task_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def delete_offboarding_task(task_id: int) -> str:
    """Delete an offboarding task template."""
    task = OffboardingTask.scoped().get_or_404(task_id)
    try:
        task.delete()
        flash(_("Offboarding task deleted."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error deleting task: %(error)s") % {"error": str(e)}, "error")
    return redirect(url_for("people_bp.team_settings", tab="offboarding"))


@blueprint.route("/people/<int:employee_id>")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def person_detail(employee_id: int) -> str:
    """Show employee details"""
    from datetime import date, timedelta
    from flask import current_app
    from system.module.registry import module_enabled

    member = (
        WorkspaceUser.scoped()
        .options(
            joinedload(WorkspaceUser.user),
            joinedload(WorkspaceUser.manager).joinedload(WorkspaceUser.user),
            selectinload(WorkspaceUser.reports).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=employee_id)
        .first_or_404()
    )

    # Determine view permissions
    is_admin = current_user.is_admin
    is_own_profile = current_user.id == member.user_id

    # Calculate stats for shortcuts (only for admin or self)
    time_stats = None
    expense_stats = None
    pto_stats = None

    if is_admin or is_own_profile:
        # Time tracking stats
        if module_enabled("Presence"):
            from modules.base.presence.models.time_entry import TimeEntry, TimeEntryStatus
            from modules.base.presence.models.leave_request import LeaveRequest, LeaveRequestStatus

            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)

            entries = TimeEntry.get_by_member(member.id, week_start, week_end)
            time_stats = {
                "hours_this_week": sum(e.hours or 0 for e in entries),
                "pending_approval": sum(1 for e in entries if e.status == TimeEntryStatus.SUBMITTED),
            }

            # PTO stats
            pending_pto = LeaveRequest.scoped().filter(
                LeaveRequest.member_id == member.id,
                LeaveRequest.status == LeaveRequestStatus.PENDING,
            ).count()
            pto_stats = {
                "pending_count": pending_pto,
            }

        # Expense stats
        if module_enabled("Finance"):
            from modules.base.finance.models.expense import Expense, ExpenseStatus, ReimbursementStatus

            user_expenses = Expense.scoped().filter_by(submitted_by_id=member.user_id)
            expense_stats = {
                "pending_count": user_expenses.filter(Expense.status == ExpenseStatus.PENDING).count(),
                "awaiting_reimbursement": user_expenses.filter(
                    Expense.status == ExpenseStatus.APPROVED,
                    Expense.reimbursement_status == ReimbursementStatus.PENDING,
                ).count(),
            }

    # Get notes for admin users
    notes = []
    if is_admin:
        notes = PersonNote.get_for_member(employee_id)

    # Get display name from plugins (e.g., nickname)
    display_name_extra = None
    if hasattr(current_app, "module_loader"):
        pm = current_app.module_loader.pm
        results = pm.hook.get_employee_display_name(employee=member)
        for result in results:
            if result:
                display_name_extra = result
                break  # Use first non-null result

    # Work schedule
    work_schedule = None
    if module_enabled("Presence"):
        from modules.base.presence.models.member_schedule import MemberSchedule

        sched = MemberSchedule.get_weekly_schedule(employee_id)
        if sched:
            work_schedule = sched

    return render_device_template(  # type: ignore[no-any-return]
        "people/desktop/people/detail.html",
        employee=member,
        is_admin=is_admin,
        is_own_profile=is_own_profile,
        time_stats=time_stats,
        expense_stats=expense_stats,
        pto_stats=pto_stats,
        display_name_extra=display_name_extra,
        notes=notes,
        work_schedule=work_schedule,
        module_home="dashboard_bp.index",
    )


@blueprint.route("/people/<int:employee_id>/update-self", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def update_self_profile(employee_id: int) -> str:
    """Allow employee to update their own profile (limited fields only)"""
    member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(id=employee_id).first_or_404()

    # Security check - only allow updating own profile
    if current_user.id != member.user_id:
        return jsonify({"error": "Not authorized"}), 403  # type: ignore[return-value]

    try:
        user = member.user

        # Fields stored on WorkspaceUser (workspace-level)
        member_fields = ["phone", "clock_pin"]
        # Fields stored on User (person-level)
        user_fields = [
            "address", "address_2", "city", "state", "zip_code",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relationship",
        ]

        for field in member_fields:
            value = request.form.get(field, "").strip()
            if hasattr(member, field):
                if field == "clock_pin" and value:
                    if len(value) != 4 or not value.isdigit():
                        return jsonify({"error": "PIN must be exactly 4 digits"}), 400  # type: ignore[return-value]
                setattr(member, field, value if value else None)

        for field in user_fields:
            value = request.form.get(field, "").strip()
            if hasattr(user, field):
                setattr(user, field, value if value else None)

        db.session.commit()
        return jsonify({"success": True, "message": "Profile updated successfully"})  # type: ignore[return-value]

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating self profile: {str(e)}")
        return jsonify({"error": str(e)}), 500  # type: ignore[return-value]


@blueprint.route("/people/<int:user_id>/permissions")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def get_user_permissions(user_id: int) -> str:
    """Get user's permissions in current workspace."""
    member = WorkspaceUser.scoped().filter_by(user_id=user_id).first_or_404()
    all_areas = ["hr", "finance", "operations"]

    return jsonify(  # type: ignore[no-any-return]
        {
            "role": member.role,
            "permissions": [
                {"name": area, "has_access": member.has_permission(area)}
                for area in all_areas
            ],
        }
    )


@blueprint.route("/people/<int:user_id>/permissions", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def update_user_permissions(user_id: int) -> str:
    """Update user's permissions in current workspace."""
    try:
        member = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(user_id=user_id).first_or_404()

        # Update role
        is_admin = request.form.get("is_admin") == "on"
        if member.role == "admin" and not is_admin:
            user = member.user
            if user.is_sole_admin:
                raise ValueError("Cannot remove last admin user")

        member.role = "admin" if is_admin else "member"

        # Update permission areas
        areas = request.form.getlist("permissions")
        member.set_permissions(areas)
        db.session.commit()

        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


# -----------------------------------------------------------------------------
# Employee Notes (admin/HR only)
# -----------------------------------------------------------------------------


@blueprint.route("/people/<int:employee_id>/notes/modal")  # type: ignore[misc]
@blueprint.route("/people/<int:employee_id>/notes/<int:note_id>/modal")  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def person_note_modal(employee_id: int, note_id: int = None) -> str:
    """Return note modal content for add or edit."""
    note = PersonNote.scoped().get_or_404(note_id) if note_id else None
    return render_template(
        "people/desktop/people/_note_modal.html",
        employee_id=employee_id,
        note=note,
    )


@blueprint.route("/people/<int:employee_id>/notes", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def create_person_note(employee_id: int) -> str:
    """Create a new note on an employee profile."""
    content = request.form.get("content", "").strip()
    if content:
        PersonNote.create(
            member_id=employee_id,
            content=content,
            user_id=current_user.id,
        )

    notes = PersonNote.get_for_member(employee_id)
    return render_template(
        "people/desktop/people/_notes_list.html",
        employee=WorkspaceUser.scoped().get(employee_id),
        notes=notes,
    )


@blueprint.route("/people/<int:employee_id>/notes/<int:note_id>", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def update_person_note(employee_id: int, note_id: int) -> str:
    """Update an existing employee note."""
    note = PersonNote.scoped().get_or_404(note_id)
    content = request.form.get("content", "").strip()
    if content:
        note.update_content(content, current_user.id)

    notes = PersonNote.get_for_member(employee_id)
    return render_template(
        "people/desktop/people/_notes_list.html",
        employee=WorkspaceUser.scoped().get(employee_id),
        notes=notes,
    )


@blueprint.route("/people/<int:employee_id>/notes/<int:note_id>/delete", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
@admin_required  # type: ignore[misc]
def delete_person_note(employee_id: int, note_id: int) -> str:
    """Soft-delete an employee note."""
    note = PersonNote.scoped().get_or_404(note_id)
    note.soft_delete(user_id=current_user.id)

    notes = PersonNote.get_for_member(employee_id)
    return render_template(
        "people/desktop/people/_notes_list.html",
        employee=WorkspaceUser.scoped().get(employee_id),
        notes=notes,
    )
