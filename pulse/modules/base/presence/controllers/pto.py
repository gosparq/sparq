# -----------------------------------------------------------------------------
# sparQ - PTO / Leave Request Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import date, datetime
from typing import Any

from flask import Blueprint, flash, g, make_response, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from sqlalchemy.orm import joinedload

from modules.base.core.models.organization_user import OrganizationUser
from system.auth.decorators import admin_required
from system.device.template import render_device_template
from system.i18n.translation import format_date, translate as _

from ..models.leave_request import LeaveRequest, LeaveRequestStatus, LeaveType


def _build_overlap_message(overlaps: list[LeaveRequest]) -> str:
    """Build a user-friendly message describing overlapping leave requests."""
    first = overlaps[0]
    return _(
        "This overlaps with your %(type)s request for %(start)s - %(end)s (%(status)s)"
    ) % {
        "type": _(first.leave_type.value),
        "start": format_date(first.start_date, "medium"),
        "end": format_date(first.end_date, "medium"),
        "status": _(first.status.value),
    }


blueprint = Blueprint(
    "pto_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.context_processor
def inject_presence_settings() -> dict[str, Any]:
    """Inject time tracking settings into all templates using this blueprint."""
    from . import presence_context
    return presence_context()


# --- Member Views ---


@blueprint.route("/")
@login_required
def index() -> ResponseReturnValue:
    """List my leave requests + pending (admin)"""
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    # Get filter parameter
    status_filter = request.args.get("status", "all")

    # Get my requests
    if status_filter == "all":
        my_requests = LeaveRequest.get_by_member(member.id)
    else:
        try:
            status = LeaveRequestStatus[status_filter.upper()]
            my_requests = LeaveRequest.get_by_member(member.id, status=status)
        except KeyError:
            my_requests = LeaveRequest.get_by_member(member.id)

    # Get pending count and upcoming count for badges
    pending_count = 0
    upcoming_count = 0
    if current_user.is_admin:
        pending_count = len(LeaveRequest.get_pending_approval())
        upcoming_count = LeaveRequest.get_upcoming_approved_count()

    return render_device_template(
        "presence/desktop/pto/index.html",
        module_home="dashboard_bp.index",
        active_page="pto",
        my_requests=my_requests,
        pending_count=pending_count,
        upcoming_count=upcoming_count,
        status_filter=status_filter,
        LeaveRequestStatus=LeaveRequestStatus,
    )


@blueprint.route("/modal/new")
@login_required
def new_request_modal() -> ResponseReturnValue:
    """Return the new PTO request modal HTML fragment."""
    return render_device_template(
        "presence/desktop/pto/partials/_new_request_modal.html",
        leave_types=LeaveType,
        today=date.today().isoformat(),
    )


@blueprint.route("/modal/clear")
@login_required
def clear_modal() -> ResponseReturnValue:
    """Clear the modal container (HTMX endpoint)."""
    return ""


@blueprint.route("/new", methods=["POST"])
@login_required
def new_request() -> ResponseReturnValue:
    """Create a new leave request (submitted from modal via HTMX)."""
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member:
        flash(_("Employee profile not found"), "error")
        return redirect(url_for("core_bp.index"))

    # Parse form data
    leave_type_str = request.form.get("leave_type")
    start_date_str = request.form.get("start_date")
    end_date_str = request.form.get("end_date")
    employee_notes = request.form.get("employee_notes", "").strip()

    def _hx_redirect(url: str) -> ResponseReturnValue:
        resp = make_response()
        resp.headers["HX-Redirect"] = url
        return resp

    # Validation
    if not leave_type_str or not start_date_str or not end_date_str:
        flash(_("Leave type, start date, and end date are required"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    try:
        leave_type = LeaveType[leave_type_str]
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except (KeyError, ValueError):
        flash(_("Invalid form data"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    if start_date < date.today():
        flash(_("Start date cannot be in the past"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    if end_date < start_date:
        flash(_("End date cannot be before start date"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    overlaps = LeaveRequest.find_overlapping(member.id, start_date, end_date)
    if overlaps:
        return render_device_template(
            "presence/desktop/pto/partials/_new_request_modal.html",
            leave_types=LeaveType,
            today=date.today().isoformat(),
            overlap_error=_build_overlap_message(overlaps),
            form_data={"leave_type": leave_type_str, "start_date": start_date_str,
                       "end_date": end_date_str, "employee_notes": employee_notes},
        ), 422

    # Create request
    try:
        leave_request = LeaveRequest.create(
            member_id=member.id,
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            employee_notes=employee_notes if employee_notes else None,
        )

        leave_request.submit()
        flash(_("Leave request submitted for approval"), "success")
        return _hx_redirect(url_for("pto_bp.index"))
    except Exception:
        flash(_("Error creating request"), "error")
        return _hx_redirect(url_for("pto_bp.index"))


@blueprint.route("/<int:request_id>")
@login_required
def detail(request_id: int) -> ResponseReturnValue:
    """View leave request details"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )

    # Check access - owner or admin
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not current_user.is_admin and (not member or leave_request.member_id != member.id):
        flash(_("Unauthorized"), "error")
        return redirect(url_for("pto_bp.index"))

    return render_device_template(
        "presence/desktop/pto/detail.html",
        module_home="dashboard_bp.index",
        active_page="pto",
        leave_request=leave_request,
        is_owner=member and leave_request.member_id == member.id,
        today=date.today(),
    )


@blueprint.route("/<int:request_id>/edit/modal")
@login_required
def edit_request_modal(request_id: int) -> ResponseReturnValue:
    """Return the edit PTO request modal HTML fragment."""
    leave_request = LeaveRequest.scoped().options(joinedload(LeaveRequest.member).joinedload(OrganizationUser.user), joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user)).filter_by(id=request_id).first_or_404()

    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or leave_request.member_id != member.id:
        flash(_("Unauthorized"), "error")
        resp = make_response()
        resp.headers["HX-Redirect"] = url_for("pto_bp.index")
        return resp

    if not leave_request.is_editable_by_member:
        flash(_("This request cannot be edited"), "error")
        resp = make_response()
        resp.headers["HX-Redirect"] = url_for("pto_bp.detail", request_id=request_id)
        return resp

    return render_device_template(
        "presence/desktop/pto/partials/_edit_request_modal.html",
        leave_request=leave_request,
        leave_types=LeaveType,
        today=date.today().isoformat(),
    )


@blueprint.route("/<int:request_id>/edit", methods=["POST"])
@login_required
def edit_request(request_id: int) -> ResponseReturnValue:
    """Edit a leave request (submitted from modal via HTMX)."""
    leave_request = LeaveRequest.scoped().options(joinedload(LeaveRequest.member).joinedload(OrganizationUser.user), joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user)).filter_by(id=request_id).first_or_404()

    # Check ownership
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or leave_request.member_id != member.id:
        flash(_("Unauthorized"), "error")
        return redirect(url_for("pto_bp.index"))

    if not leave_request.is_editable_by_member:
        flash(_("This request cannot be edited"), "error")
        return redirect(url_for("pto_bp.detail", request_id=request_id))

    # Parse form data
    leave_type_str = request.form.get("leave_type")
    start_date_str = request.form.get("start_date")
    end_date_str = request.form.get("end_date")
    employee_notes = request.form.get("employee_notes", "").strip()

    def _hx_redirect(url: str) -> ResponseReturnValue:
        resp = make_response()
        resp.headers["HX-Redirect"] = url
        return resp

    try:
        leave_type = LeaveType[leave_type_str]
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except (KeyError, ValueError):
        flash(_("Invalid form data"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    if start_date < date.today():
        flash(_("Start date cannot be in the past"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    if end_date < start_date:
        flash(_("End date cannot be before start date"), "error")
        return _hx_redirect(url_for("pto_bp.index"))

    overlaps = LeaveRequest.find_overlapping(
        member.id, start_date, end_date, exclude_id=leave_request.id
    )
    if overlaps:
        return render_device_template(
            "presence/desktop/pto/partials/_edit_request_modal.html",
            leave_request=leave_request,
            leave_types=LeaveType,
            today=date.today().isoformat(),
            overlap_error=_build_overlap_message(overlaps),
            form_data={"leave_type": leave_type_str, "start_date": start_date_str,
                       "end_date": end_date_str, "employee_notes": employee_notes},
        ), 422

    try:
        leave_request.update(
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            employee_notes=employee_notes if employee_notes else None,
        )

        if leave_request.status == LeaveRequestStatus.DRAFT:
            leave_request.submit()
            flash(_("Leave request submitted for approval"), "success")
        else:
            flash(_("Leave request updated"), "success")

        return _hx_redirect(url_for("pto_bp.index"))
    except Exception:
        flash(_("Error updating request"), "error")
        return _hx_redirect(url_for("pto_bp.index"))


@blueprint.route("/<int:request_id>/submit", methods=["POST"])
@login_required
def submit_request(request_id: int) -> ResponseReturnValue:
    """Submit a draft request for approval"""
    leave_request = LeaveRequest.scoped().options(joinedload(LeaveRequest.member).joinedload(OrganizationUser.user), joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user)).filter_by(id=request_id).first_or_404()

    # Check ownership
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or leave_request.member_id != member.id:
        flash(_("Unauthorized"), "error")
        return redirect(url_for("pto_bp.index"))

    try:
        leave_request.submit()
        flash(_("Leave request submitted for approval"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("pto_bp.index"))


@blueprint.route("/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_request(request_id: int) -> ResponseReturnValue:
    """Cancel a leave request"""
    leave_request = LeaveRequest.scoped().options(joinedload(LeaveRequest.member).joinedload(OrganizationUser.user), joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user)).filter_by(id=request_id).first_or_404()

    # Check ownership
    member = OrganizationUser.get_for_user(current_user.id, g.organization_id)
    if not member or leave_request.member_id != member.id:
        flash(_("Unauthorized"), "error")
        return redirect(url_for("pto_bp.index"))

    try:
        leave_request.cancel()
        flash(_("Leave request cancelled"), "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("pto_bp.index"))


# --- Admin Approval Routes ---


@blueprint.route("/approve")
@login_required
@admin_required
def approval_queue() -> ResponseReturnValue:
    """Admin view of pending leave requests"""
    pending_requests = LeaveRequest.get_pending_approval()
    upcoming_count = LeaveRequest.get_upcoming_approved_count()

    return render_device_template(
        "presence/desktop/pto/approve.html",
        module_home="dashboard_bp.index",
        active_page="pto",
        pending_requests=pending_requests,
        upcoming_count=upcoming_count,
    )


@blueprint.route("/scheduled")
@login_required
@admin_required
def scheduled() -> ResponseReturnValue:
    """Admin view of all approved leave requests"""
    upcoming = LeaveRequest.get_upcoming_approved()
    past, has_more_past = LeaveRequest.get_past_approved(limit=5, offset=0)
    pending_count = len(LeaveRequest.get_pending_approval())

    return render_device_template(
        "presence/desktop/pto/scheduled.html",
        module_home="dashboard_bp.index",
        active_page="pto",
        upcoming=upcoming,
        past=past,
        has_more_past=has_more_past,
        past_offset=5,
        pending_count=pending_count,
    )


@blueprint.route("/scheduled/past")
@login_required
@admin_required
def scheduled_past() -> ResponseReturnValue:
    """HTMX partial: load more past approved leave requests"""
    offset = request.args.get("offset", 0, type=int)
    past, has_more_past = LeaveRequest.get_past_approved(limit=5, offset=offset)

    return render_template(
        "presence/desktop/pto/partials/_past_items.html",
        past=past,
        has_more_past=has_more_past,
        past_offset=offset + 5,
    )


@blueprint.route("/<int:request_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_request(request_id: int) -> ResponseReturnValue:
    """Approve a leave request"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )
    notes = request.form.get("notes", "").strip()

    # Block if another request for this member is already approved for overlapping dates
    overlaps = LeaveRequest.find_overlapping(
        leave_request.member_id,
        leave_request.start_date,
        leave_request.end_date,
        statuses=[LeaveRequestStatus.APPROVED],
        exclude_id=leave_request.id,
    )
    if overlaps:
        flash(_build_overlap_message(overlaps), "error")
        if request.form.get("redirect") == "detail":
            return redirect(url_for("pto_bp.detail", request_id=request_id))
        return redirect(url_for("pto_bp.approval_queue"))

    try:
        leave_request.approve(current_user.id, notes if notes else None)
        flash(_("Leave request for %(name)s approved") % {"name": leave_request.member.user.first_name}, "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    # Check if coming from approval queue or detail page
    if request.form.get("redirect") == "detail":
        return redirect(url_for("pto_bp.detail", request_id=request_id))
    return redirect(url_for("pto_bp.approval_queue"))


@blueprint.route("/<int:request_id>/deny", methods=["POST"])
@login_required
@admin_required
def deny_request(request_id: int) -> ResponseReturnValue:
    """Deny a leave request"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )
    notes = request.form.get("notes", "").strip()

    if not notes:
        flash(_("A reason is required when denying a request"), "error")
        return redirect(url_for("pto_bp.approval_queue"))

    try:
        leave_request.deny(current_user.id, notes)
        flash(_("Leave request for %(name)s denied") % {"name": leave_request.member.user.first_name}, "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    if request.form.get("redirect") == "detail":
        return redirect(url_for("pto_bp.detail", request_id=request_id))
    return redirect(url_for("pto_bp.approval_queue"))


@blueprint.route("/<int:request_id>/request-changes", methods=["POST"])
@login_required
@admin_required
def request_changes(request_id: int) -> ResponseReturnValue:
    """Send feedback to member without approving/denying"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )
    notes = request.form.get("notes", "").strip()

    if not notes:
        flash(_("A note is required when requesting changes"), "error")
        return redirect(url_for("pto_bp.approval_queue"))

    try:
        leave_request.request_changes(current_user.id, notes)
        flash(_("Feedback sent to %(name)s") % {"name": leave_request.member.user.first_name}, "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    if request.form.get("redirect") == "detail":
        return redirect(url_for("pto_bp.detail", request_id=request_id))
    return redirect(url_for("pto_bp.approval_queue"))


@blueprint.route("/<int:request_id>/unapprove", methods=["POST"])
@login_required
@admin_required
def unapprove_request(request_id: int) -> ResponseReturnValue:
    """Revert approved request back to pending"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )

    try:
        leave_request.unapprove(current_user.id)
        flash(_("Leave request for %(name)s reverted to pending") % {"name": leave_request.member.user.first_name}, "success")
    except ValueError as e:
        flash(_(str(e)), "error")

    return redirect(url_for("pto_bp.detail", request_id=request_id))


# --- Admin Edit Routes ---


@blueprint.route("/<int:request_id>/admin-edit", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit(request_id: int) -> ResponseReturnValue:
    """Admin can edit any request"""
    leave_request = (
        LeaveRequest.scoped()
        .options(
            joinedload(LeaveRequest.member).joinedload(OrganizationUser.user),
            joinedload(LeaveRequest.reviewed_by).joinedload(OrganizationUser.user),
        )
        .filter_by(id=request_id)
        .first_or_404()
    )

    if request.method == "POST":
        leave_type_str = request.form.get("leave_type")
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")
        employee_notes = request.form.get("employee_notes", "").strip()
        status_str = request.form.get("status")

        try:
            leave_type = LeaveType[leave_type_str]
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            new_status = LeaveRequestStatus[status_str]
        except (KeyError, ValueError):
            flash(_("Invalid form data"), "error")
            return redirect(url_for("pto_bp.admin_edit", request_id=request_id))

        if end_date < start_date:
            flash(_("End date cannot be before start date"), "error")
            return redirect(url_for("pto_bp.admin_edit", request_id=request_id))

        if new_status in (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED):
            check_statuses = (
                [LeaveRequestStatus.APPROVED]
                if new_status == LeaveRequestStatus.APPROVED
                else [LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED]
            )
            overlaps = LeaveRequest.find_overlapping(
                leave_request.member_id, start_date, end_date,
                statuses=check_statuses, exclude_id=leave_request.id,
            )
            if overlaps:
                flash(_build_overlap_message(overlaps), "error")
                return redirect(url_for("pto_bp.admin_edit", request_id=request_id))

        leave_request.admin_update(
            leave_type=leave_type,
            start_date=start_date,
            end_date=end_date,
            employee_notes=employee_notes if employee_notes else None,
            status=new_status,
        )

        flash(_("Leave request updated"), "success")
        return redirect(url_for("pto_bp.detail", request_id=request_id))

    return render_device_template(
        "presence/desktop/pto/admin_edit.html",
        module_home="dashboard_bp.index",
        active_page="pto",
        leave_request=leave_request,
        leave_types=LeaveType,
        statuses=LeaveRequestStatus,
    )
