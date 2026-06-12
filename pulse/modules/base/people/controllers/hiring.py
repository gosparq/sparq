# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Hiring routes (merged into Team module).
#     All routes are prefixed with /hiring under the team module.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import mimetypes
import os

from flask import g, render_template, request, redirect, url_for, flash, make_response, send_file, session
from markupsafe import escape
from flask_login import login_required, current_user

from datetime import datetime
from sqlalchemy.orm import joinedload, selectinload
from system.db.database import db
from system.device import is_mobile
from system.device.template import render_device_template
from system.i18n.translation import translate as _
from modules.base.resources.models.attachment import Attachment
from modules.base.resources.services import storage

from . import blueprint  # Import the team blueprint
from ..decorators import admin_required

from ..models.hiring import (
    JobPosting, JobStatus, JobType,
    Candidate, CandidateSource,
    Application, ApplicationStatus, APPLICATION_STATUS_ORDER,
    Interview, InterviewType, InterviewStatus, InterviewRecommendation,
    ApplicationActivity, ActivityType,
)


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------


@blueprint.route("/hiring")
@blueprint.route("/hiring/")
@login_required
@admin_required
def hiring_index():
    """Hiring dashboard - shows jobs overview on mobile, redirects to jobs on desktop"""
    if is_mobile():
        # Mobile: show dashboard with jobs and recent applications
        jobs_list = JobPosting.scoped().order_by(JobPosting.created_at.desc()).all()

        # Get recent applications across all jobs
        recent_applications = Application.scoped().order_by(
            Application.created_at.desc()
        ).limit(10).all()

        return render_device_template(
            "people/desktop/hiring/index.html",
            active_page="dashboard",
            title="Hiring",
            page_icon="fa-solid fa-user-plus",
            icon_color=g.workspace_color,
            module_home="people_bp.hiring_index",
            jobs=jobs_list,
            recent_applications=recent_applications,
            JobStatus=JobStatus,
        )

    # Desktop: redirect to jobs list
    return redirect(url_for("people_bp.hiring_jobs"))


# -----------------------------------------------------------------------------
# Jobs CRUD
# -----------------------------------------------------------------------------


@blueprint.route("/hiring/jobs")
@login_required
@admin_required
def hiring_jobs():
    """List all jobs with filters"""
    # Get filter parameters
    status_filter = request.args.get("status", "all")

    # Build query
    query = JobPosting.scoped().options(
        selectinload(JobPosting.applications),
        joinedload(JobPosting.hiring_manager),
    )

    if status_filter == "open":
        query = query.filter_by(status=JobStatus.OPEN)
    elif status_filter == "draft":
        query = query.filter_by(status=JobStatus.DRAFT)
    elif status_filter == "closed":
        query = query.filter_by(status=JobStatus.CLOSED)
    elif status_filter == "on_hold":
        query = query.filter_by(status=JobStatus.ON_HOLD)

    # Order: open jobs first when viewing all, otherwise by date
    if status_filter == "all":
        from sqlalchemy import case
        status_order = case(
            (JobPosting.status == JobStatus.OPEN, 0),
            (JobPosting.status == JobStatus.DRAFT, 1),
            (JobPosting.status == JobStatus.ON_HOLD, 2),
            (JobPosting.status == JobStatus.CLOSED, 3),
            else_=4,
        )
        jobs_list = query.order_by(status_order, JobPosting.created_at.desc()).all()
    else:
        jobs_list = query.order_by(JobPosting.created_at.desc()).all()

    # Get counts for filter tabs
    counts = {
        "all": JobPosting.scoped().count(),
        "open": JobPosting.scoped().filter_by(status=JobStatus.OPEN).count(),
        "draft": JobPosting.scoped().filter_by(status=JobStatus.DRAFT).count(),
        "closed": JobPosting.scoped().filter_by(status=JobStatus.CLOSED).count(),
        "on_hold": JobPosting.scoped().filter_by(status=JobStatus.ON_HOLD).count(),
    }

    # Group jobs by status for kanban board view
    jobs_by_status = {status: [] for status in [JobStatus.DRAFT, JobStatus.OPEN, JobStatus.ON_HOLD, JobStatus.CLOSED]}
    for job in jobs_list:
        jobs_by_status[job.status].append(job)

    return render_template(
        "people/desktop/hiring/jobs/index.html",
        active_page="jobs",
        title="Jobs",
        page_icon="fa-solid fa-briefcase",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        jobs=jobs_list,
        jobs_by_status=jobs_by_status,
        current_status=status_filter,
        counts=counts,
        JobStatus=JobStatus,
    )


@blueprint.route("/hiring/jobs/new", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_job_new():
    """Create a new job posting"""
    if request.method == "POST":
        # Create the job
        job = JobPosting(
            title=request.form.get("title"),
            department=request.form.get("department") or None,
            location=request.form.get("location") or None,
            job_type=JobType[request.form.get("job_type", "FULL_TIME")],
            salary_min=request.form.get("salary_min") or None,
            salary_max=request.form.get("salary_max") or None,
            description=request.form.get("description") or None,
            requirements=request.form.get("requirements") or None,
            status=JobStatus.DRAFT,
        )

        db.session.add(job)
        db.session.commit()

        flash(_("Job posting created successfully!"), "success")
        return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))

    # Get employees for hiring manager dropdown
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus

    employees = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()

    return render_template(
        "people/desktop/hiring/jobs/form.html",
        active_page="jobs",
        title="New Job",
        page_icon="fa-solid fa-briefcase",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        job=None,
        employees=employees,
        JobType=JobType,
    )


@blueprint.route("/hiring/jobs/<int:job_id>")
@login_required
@admin_required
def hiring_job_detail(job_id):
    """View job details with candidate pipeline"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    # Get pipeline data for kanban view
    pipeline = Application.get_pipeline_for_job(job_id)

    return render_template(
        "people/desktop/hiring/jobs/detail.html",
        active_page="jobs",
        title=job.title,
        page_icon="fa-solid fa-briefcase",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        job=job,
        pipeline=pipeline,
        JobStatus=JobStatus,
        ApplicationStatus=ApplicationStatus,
        APPLICATION_STATUS_ORDER=APPLICATION_STATUS_ORDER,
    )


@blueprint.route("/hiring/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_job_edit(job_id):
    """Edit a job posting"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    if request.method == "POST":
        job.title = request.form.get("title")
        job.department = request.form.get("department") or None
        job.location = request.form.get("location") or None
        job.job_type = JobType[request.form.get("job_type", "FULL_TIME")]
        job.salary_min = request.form.get("salary_min") or None
        job.salary_max = request.form.get("salary_max") or None
        job.description = request.form.get("description") or None
        job.requirements = request.form.get("requirements") or None

        # Update hiring manager if provided
        hiring_manager_id = request.form.get("hiring_manager_id")
        job.hiring_manager_id = int(hiring_manager_id) if hiring_manager_id else None

        db.session.commit()

        flash(_("Job posting updated successfully!"), "success")
        return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))

    # Get employees for hiring manager dropdown
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus

    employees = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()

    return render_template(
        "people/desktop/hiring/jobs/form.html",
        active_page="jobs",
        title="Edit Job",
        page_icon="fa-solid fa-briefcase",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        job=job,
        employees=employees,
        JobType=JobType,
    )


@blueprint.route("/hiring/jobs/<int:job_id>/publish", methods=["POST"])
@login_required
@admin_required
def hiring_job_publish(job_id):
    """Publish a job (set status to Open)"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    job.publish()
    flash(_("Job '%(title)s' has been published!") % {"title": job.title}, "success")
    return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))


@blueprint.route("/hiring/jobs/<int:job_id>/close", methods=["POST"])
@login_required
@admin_required
def hiring_job_close(job_id):
    """Close a job posting"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    job.close()
    flash(_("Job '%(title)s' has been closed.") % {"title": job.title}, "success")
    return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))


@blueprint.route("/hiring/jobs/<int:job_id>/hold", methods=["POST"])
@login_required
@admin_required
def hiring_job_hold(job_id):
    """Put a job on hold"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    job.hold()
    flash(_("Job '%(title)s' has been put on hold.") % {"title": job.title}, "info")
    return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))


@blueprint.route("/hiring/jobs/<int:job_id>/reopen", methods=["POST"])
@login_required
@admin_required
def hiring_job_reopen(job_id):
    """Reopen a closed or on-hold job"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    job.publish()  # This sets status to OPEN and updates published_at
    flash(_("Job '%(title)s' has been reopened!") % {"title": job.title}, "success")
    return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))


@blueprint.route("/hiring/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
@admin_required
def hiring_job_delete(job_id):
    """Delete a job posting (draft only)"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    if job.status != JobStatus.DRAFT:
        flash(_("Only draft jobs can be deleted. Close the job first."), "error")
        return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))

    title = job.title
    db.session.delete(job)
    db.session.commit()

    flash(_("Job '%(title)s' has been deleted.") % {"title": title}, "success")
    return redirect(url_for("people_bp.hiring_jobs"))


# -----------------------------------------------------------------------------
# Job Status (unified endpoint for drag-drop)
# -----------------------------------------------------------------------------


# Valid job status transitions: (from_status, to_status)
VALID_JOB_TRANSITIONS = {
    (JobStatus.DRAFT, JobStatus.OPEN),
    (JobStatus.OPEN, JobStatus.ON_HOLD),
    (JobStatus.OPEN, JobStatus.CLOSED),
    (JobStatus.ON_HOLD, JobStatus.OPEN),
    (JobStatus.CLOSED, JobStatus.OPEN),
}


@blueprint.route("/hiring/jobs/<int:job_id>/status", methods=["POST"])
@login_required
@admin_required
def hiring_job_status(job_id):
    """Change job status via drag-drop or form submission"""
    job = JobPosting.get_by_id(job_id)
    if not job:
        if is_htmx_request():
            return "", 404
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    new_status_str = request.form.get("status")
    try:
        new_status = JobStatus[new_status_str]
    except (KeyError, TypeError):
        if is_htmx_request():
            return "Invalid status", 400
        flash(_("Invalid status"), "error")
        return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))

    # Validate transition
    if (job.status, new_status) not in VALID_JOB_TRANSITIONS:
        if is_htmx_request():
            return f"Cannot move from {job.status.value} to {new_status.value}", 400
        flash(_("Cannot move from %(from_status)s to %(to_status)s") % {"from_status": job.status.value, "to_status": new_status.value}, "error")
        return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))

    # Apply the transition using existing model methods
    if new_status == JobStatus.OPEN:
        job.publish()
    elif new_status == JobStatus.ON_HOLD:
        job.hold()
    elif new_status == JobStatus.CLOSED:
        job.close()

    if is_htmx_request():
        return "", 200

    flash(_("Job '%(title)s' status changed to %(status)s") % {"title": job.title, "status": new_status.value}, "success")
    return redirect(url_for("people_bp.hiring_job_detail", job_id=job.id))


# -----------------------------------------------------------------------------
# Pipeline (overall view)
# -----------------------------------------------------------------------------


@blueprint.route("/hiring/pipeline")
@login_required
@admin_required
def hiring_pipeline():
    """Overall pipeline view across all jobs"""
    # Get all applications grouped by status
    all_applications = Application.scoped().options(
        joinedload(Application.candidate),
        joinedload(Application.job_posting),
    ).order_by(Application.created_at.desc()).all()
    pipeline = {status: [] for status in APPLICATION_STATUS_ORDER}
    for app in all_applications:
        pipeline[app.status].append(app)

    return render_template(
        "people/desktop/hiring/pipeline/index.html",
        active_page="pipeline",
        title="Pipeline",
        page_icon="fa-solid fa-columns",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        pipeline=pipeline,
        all_applications=all_applications,
        ApplicationStatus=ApplicationStatus,
        APPLICATION_STATUS_ORDER=APPLICATION_STATUS_ORDER,
    )


# -----------------------------------------------------------------------------
# Candidates CRUD
# -----------------------------------------------------------------------------


@blueprint.route("/hiring/candidates")
@login_required
@admin_required
def hiring_candidates():
    """List all candidates"""
    search_query = request.args.get("q", "").strip()

    if search_query:
        candidates_list = Candidate.search(search_query)
    else:
        candidates_list = Candidate.get_all()

    # Use mobile-optimized list template on mobile
    if is_mobile():
        return render_device_template(
            "people/desktop/hiring/candidates.html",
            active_page="candidates",
            title="Candidates",
            page_icon="fa-solid fa-users",
            icon_color=g.workspace_color,
            module_home="people_bp.hiring_index",
            candidates=candidates_list,
            search_query=search_query,
            CandidateSource=CandidateSource,
        )

    return render_template(
        "people/desktop/hiring/candidates/index.html",
        active_page="candidates",
        title="Candidates",
        page_icon="fa-solid fa-users",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        candidates=candidates_list,
        search_query=search_query,
        CandidateSource=CandidateSource,
    )


@blueprint.route("/hiring/candidates/parse-resume", methods=["POST"])
@login_required
@admin_required
def hiring_parse_resume():
    """Parse uploaded resume and return form data via HTMX.

    This endpoint:
    1. Receives the uploaded resume file
    2. Sends it to the parser API
    3. Stores the file temporarily in session for later attachment
    4. Returns HTML with JS to populate form fields
    """
    import logging
    from ..services.resume_parser import parse_resume as do_parse, is_supported_file

    file = request.files.get("resume_file")
    if not file or not file.filename:
        return '<div class="alert alert-warning alert-sm py-1 small">No file selected</div>'

    if not is_supported_file(file.filename):
        return '<div class="alert alert-danger alert-sm py-1 small">Unsupported format. Use PDF, DOC, DOCX, TXT, or RTF</div>'

    # Parse the resume
    result = do_parse(file)
    logging.info(f"Resume parse result: success={result.success}, error={result.error_message}")

    # Save file to temp location for later attachment
    # Reset file position after parsing
    file.seek(0)

    # Get file info
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset

    mime_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"

    # Create attachment record
    attachment = Attachment.create(
        filename=file.filename,
        mime_type=mime_type,
        size_bytes=file_size,
    )

    # Save file to resumes directory
    storage.save_to_resumes(file, attachment)

    # Store attachment ID in session for the form submission
    session["pending_resume_id"] = attachment.id

    if not result.success:
        # File saved but couldn't be parsed - still allow manual entry
        return f'''
        <div class="alert alert-warning alert-sm py-1 small mb-2">
            <i class="fas fa-exclamation-triangle me-1"></i>
            Could not parse resume: {escape(result.error_message)}. Please fill in the form manually.
        </div>
        <div class="alert alert-info alert-sm py-1 small">
            <i class="fas fa-paperclip me-1"></i>
            Resume attached: <strong>{escape(file.filename)}</strong>
        </div>
        <script>document.getElementById('resume_uploaded').value = '{attachment.id}';</script>
        '''

    # Build form data from parsed result
    form_data = result.to_form_data()

    # All form fields that can be populated
    all_fields = ['first_name', 'last_name', 'email', 'phone', 'city', 'state',
                  'current_title', 'current_company', 'linkedin_url']

    # Generate JS to clear all fields first, then populate with new data
    js_updates = []
    for field in all_fields:
        if field in form_data:
            # Escape single quotes in values
            escaped_value = form_data[field].replace("'", "\\'").replace("\n", " ")
            js_updates.append(f"document.getElementById('{field}').value = '{escaped_value}';")
        else:
            # Clear fields not in parsed data
            js_updates.append(f"document.getElementById('{field}').value = '';")

    js_script = "\n".join(js_updates)

    # Count filled fields
    filled_count = len(form_data)

    return f'''
    <div class="alert alert-success alert-sm py-1 small mb-2">
        <i class="fas fa-check-circle me-1"></i>
        Parsed {filled_count} field(s) from resume. Review and complete the form below.
    </div>
    <div class="alert alert-info alert-sm py-1 small">
        <i class="fas fa-paperclip me-1"></i>
        Resume attached: <strong>{escape(file.filename)}</strong>
    </div>
    <script>
        {js_script}
        document.getElementById('resume_uploaded').value = '{attachment.id}';
    </script>
    '''


@blueprint.route("/hiring/candidates/new", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_candidate_new():
    """Create a new candidate"""
    if request.method == "POST":
        # Check if email already exists
        email = request.form.get("email")
        existing = Candidate.get_by_email(email)
        if existing:
            flash(_("A candidate with email %(email)s already exists.") % {"email": email}, "error")
            return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=existing.id))

        candidate = Candidate(
            first_name=request.form.get("first_name"),
            last_name=request.form.get("last_name"),
            email=email,
            phone=request.form.get("phone") or None,
            city=request.form.get("city") or None,
            state=request.form.get("state") or None,
            current_company=request.form.get("current_company") or None,
            current_title=request.form.get("current_title") or None,
            linkedin_url=request.form.get("linkedin_url") or None,
            source=CandidateSource[request.form.get("source", "OTHER")],
            source_detail=request.form.get("source_detail") or None,
            notes=request.form.get("notes") or None,
        )

        # Handle resume attachment
        resume_id = request.form.get("resume_uploaded")
        if resume_id:
            try:
                attachment = Attachment.get_by_id(int(resume_id))
                if attachment:
                    candidate.resume_id = attachment.id
            except (ValueError, TypeError):
                pass
        elif "pending_resume_id" in session:
            # Fallback to session-stored resume ID
            try:
                attachment = Attachment.get_by_id(session["pending_resume_id"])
                if attachment:
                    candidate.resume_id = attachment.id
                del session["pending_resume_id"]
            except (ValueError, TypeError, KeyError):
                pass

        db.session.add(candidate)
        db.session.commit()

        flash(_("Candidate added successfully!"), "success")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate.id))

    # Clear any pending resume from previous attempts
    session.pop("pending_resume_id", None)

    # Get open jobs for quick apply dropdown
    open_jobs = JobPosting.scoped().filter_by(status=JobStatus.OPEN).all()

    return render_template(
        "people/desktop/hiring/candidates/form.html",
        active_page="candidates",
        title="New Candidate",
        page_icon="fa-solid fa-user-plus",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        candidate=None,
        CandidateSource=CandidateSource,
        open_jobs=open_jobs,
    )


@blueprint.route("/hiring/candidates/<int:candidate_id>")
@login_required
@admin_required
def hiring_candidate_detail(candidate_id):
    """View candidate details"""
    candidate = Candidate.get_by_id(candidate_id)
    if not candidate:
        flash(_("Candidate not found"), "error")
        return redirect(url_for("people_bp.hiring_candidates"))

    # Get open jobs for apply dropdown
    open_jobs = JobPosting.scoped().filter_by(status=JobStatus.OPEN).all()

    return render_template(
        "people/desktop/hiring/candidates/detail.html",
        active_page="candidates",
        title=candidate.full_name,
        page_icon="fa-solid fa-user",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        candidate=candidate,
        open_jobs=open_jobs,
        ApplicationStatus=ApplicationStatus,
    )


@blueprint.route("/hiring/candidates/<int:candidate_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_candidate_edit(candidate_id):
    """Edit a candidate"""
    candidate = Candidate.get_by_id(candidate_id)
    if not candidate:
        flash(_("Candidate not found"), "error")
        return redirect(url_for("people_bp.hiring_candidates"))

    if request.method == "POST":
        # Check if email changed and already exists
        new_email = request.form.get("email")
        if new_email != candidate.email:
            existing = Candidate.get_by_email(new_email)
            if existing:
                flash(_("A candidate with email %(email)s already exists.") % {"email": new_email}, "error")
                return redirect(url_for("people_bp.hiring_candidate_edit", candidate_id=candidate_id))

        candidate.first_name = request.form.get("first_name")
        candidate.last_name = request.form.get("last_name")
        candidate.email = new_email
        candidate.phone = request.form.get("phone") or None
        candidate.city = request.form.get("city") or None
        candidate.state = request.form.get("state") or None
        candidate.current_company = request.form.get("current_company") or None
        candidate.current_title = request.form.get("current_title") or None
        candidate.linkedin_url = request.form.get("linkedin_url") or None
        candidate.source = CandidateSource[request.form.get("source", "OTHER")]
        candidate.source_detail = request.form.get("source_detail") or None
        candidate.notes = request.form.get("notes") or None

        db.session.commit()

        flash(_("Candidate updated successfully!"), "success")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate.id))

    return render_template(
        "people/desktop/hiring/candidates/form.html",
        active_page="candidates",
        title="Edit Candidate",
        page_icon="fa-solid fa-user-edit",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        candidate=candidate,
        CandidateSource=CandidateSource,
        open_jobs=[],
    )


@blueprint.route("/hiring/candidates/<int:candidate_id>/delete", methods=["POST"])
@login_required
@admin_required
def hiring_candidate_delete(candidate_id):
    """Delete a candidate"""
    candidate = Candidate.get_by_id(candidate_id)
    if not candidate:
        flash(_("Candidate not found"), "error")
        return redirect(url_for("people_bp.hiring_candidates"))

    # Check if candidate has any applications
    if candidate.applications:
        flash(_("Cannot delete candidate with existing applications."), "error")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate.id))

    name = candidate.full_name
    db.session.delete(candidate)
    db.session.commit()

    flash(_("Candidate '%(name)s' has been deleted.") % {"name": name}, "success")
    return redirect(url_for("people_bp.hiring_candidates"))


@blueprint.route("/hiring/candidates/<int:candidate_id>/apply", methods=["POST"])
@login_required
@admin_required
def hiring_candidate_apply(candidate_id):
    """Apply a candidate to a job"""
    candidate = Candidate.get_by_id(candidate_id)
    if not candidate:
        flash(_("Candidate not found"), "error")
        return redirect(url_for("people_bp.hiring_candidates"))

    job_id = request.form.get("job_id")
    if not job_id:
        flash(_("Please select a job"), "error")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))

    job = JobPosting.get_by_id(int(job_id))
    if not job:
        flash(_("Job not found"), "error")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))

    # Check if already applied
    existing = Application.scoped().filter_by(candidate_id=candidate.id, job_posting_id=job.id).first()
    if existing:
        flash(_("Candidate already applied to '%(title)s'") % {"title": job.title}, "warning")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))

    # Create application
    application = Application(
        candidate_id=candidate.id,
        job_posting_id=job.id,
        status=ApplicationStatus.NEW,
    )
    db.session.add(application)
    db.session.commit()

    flash(_("Candidate applied to '%(title)s' successfully!") % {"title": job.title}, "success")
    return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))


@blueprint.route("/hiring/candidates/<int:candidate_id>/resume")
@login_required
@admin_required
def hiring_download_resume(candidate_id):
    """Download a candidate's resume"""
    candidate = Candidate.get_by_id(candidate_id)
    if not candidate:
        flash(_("Candidate not found"), "error")
        return redirect(url_for("people_bp.hiring_candidates"))

    if not candidate.resume:
        flash(_("No resume attached to this candidate"), "error")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))

    # Get file path
    file_path = storage.get_resume_path(candidate.resume)

    if not os.path.exists(file_path):
        flash(_("Resume file not found"), "error")
        return redirect(url_for("people_bp.hiring_candidate_detail", candidate_id=candidate_id))

    return send_file(
        file_path,
        download_name=candidate.resume.filename,
        as_attachment=True,
        mimetype=candidate.resume.mime_type,
    )


# -----------------------------------------------------------------------------
# Applications - Status Changes and Pipeline
# -----------------------------------------------------------------------------


@blueprint.route("/hiring/applications/<int:application_id>")
@login_required
@admin_required
def hiring_application_detail(application_id):
    """View application details with timeline"""
    application = Application.get_by_id(application_id)
    if not application:
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    return render_template(
        "people/desktop/hiring/applications/detail.html",
        active_page="jobs",
        title=f"{application.candidate.full_name} - {application.job_posting.title}",
        page_icon="fa-solid fa-user",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        application=application,
        ApplicationStatus=ApplicationStatus,
    )


@blueprint.route("/hiring/applications/<int:application_id>/status", methods=["POST"])
@login_required
@admin_required
def hiring_application_status(application_id):
    """Change application status"""
    application = Application.get_by_id(application_id)
    if not application:
        if is_htmx_request():
            return "", 404
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    new_status = request.form.get("status")
    reason = request.form.get("reason")

    try:
        status_enum = ApplicationStatus[new_status]
        application.change_status(status_enum, user_id=current_user.id, reason=reason)
    except (KeyError, ValueError):
        if is_htmx_request():
            return "", 400
        flash(_("Invalid status"), "error")
        return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))

    # Return partial for HTMX or redirect
    if is_htmx_request():
        return render_template(
            "people/desktop/hiring/partials/_status_card.html",
            application=application,
            ApplicationStatus=ApplicationStatus,
        )

    flash(_("Status updated to %(status)s") % {"status": status_enum.value}, "success")
    return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))


@blueprint.route("/hiring/applications/<int:application_id>/rate", methods=["POST"])
@login_required
@admin_required
def hiring_application_rate(application_id):
    """Set application rating"""
    application = Application.get_by_id(application_id)
    if not application:
        if is_htmx_request():
            return "", 404
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    rating = request.form.get("rating")
    try:
        rating_int = int(rating)
        if 1 <= rating_int <= 5:
            application.set_rating(rating_int, user_id=current_user.id)
        else:
            if is_htmx_request():
                return "", 400
            flash(_("Rating must be between 1 and 5"), "error")
            return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))
    except (TypeError, ValueError):
        if is_htmx_request():
            return "", 400
        flash(_("Invalid rating"), "error")
        return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))

    # Return partial for HTMX or redirect
    if is_htmx_request():
        return render_template(
            "people/desktop/hiring/partials/_rating.html",
            application=application,
        )

    flash(_("Rating set to %(rating)s stars") % {"rating": rating_int}, "success")
    return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))


@blueprint.route("/hiring/applications/<int:application_id>/note", methods=["POST"])
@login_required
@admin_required
def hiring_application_note(application_id):
    """Add a note to an application"""
    application = Application.get_by_id(application_id)
    if not application:
        if is_htmx_request():
            return "", 404
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    note = request.form.get("note", "").strip()
    if note:
        application.add_note(note, user_id=current_user.id)
    else:
        if is_htmx_request():
            return "", 400
        flash(_("Note cannot be empty"), "error")
        return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))

    # Return partial for HTMX or redirect
    if is_htmx_request():
        return render_template(
            "people/desktop/hiring/partials/_activity_timeline.html",
            application=application,
        )

    flash(_("Note added"), "success")
    return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=application_id))


@blueprint.route("/hiring/applications/<int:application_id>/reject", methods=["POST"])
@login_required
@admin_required
def hiring_application_reject(application_id):
    """Quick reject an application"""
    application = Application.get_by_id(application_id)
    if not application:
        if is_htmx_request():
            return "", 404
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    reason = request.form.get("reason", "").strip()
    application.change_status(ApplicationStatus.REJECTED, user_id=current_user.id, reason=reason)

    # For HTMX, return redirect header to job detail
    if is_htmx_request():
        response = make_response()
        response.headers["HX-Redirect"] = url_for("people_bp.hiring_job_detail", job_id=application.job_posting_id)
        flash(_("Application rejected"), "success")
        return response

    flash(_("Application rejected"), "success")
    return redirect(request.referrer or url_for("people_bp.hiring_job_detail", job_id=application.job_posting_id))


@blueprint.route("/hiring/applications/<int:application_id>/hire", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_application_hire(application_id):
    """Mark application as hired and create onboarding record"""
    application = Application.get_by_id(application_id)
    if not application:
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    # Check if already hired
    if application.status == ApplicationStatus.HIRED:
        flash(_("This application is already marked as hired"), "warning")
        return redirect(url_for("people_bp.hiring_application_detail", application_id=application_id))

    if request.method == "POST":
        from ..models.onboarding import OnboardingRecord, OnboardingType

        # Determine onboarding type from job type
        job_type = application.job_posting.job_type
        if job_type and job_type.name == "CONTRACT":
            onboarding_type = OnboardingType.CONTRACTOR
        else:
            onboarding_type = OnboardingType.W2

        # Get form values (with defaults from candidate/job)
        start_date_str = request.form.get("start_date")
        start_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        salary = request.form.get("salary") or None
        if salary:
            try:
                salary = float(salary)
            except ValueError:
                salary = None

        # Create onboarding record
        onboarding = OnboardingRecord.create(
            first_name=application.candidate.first_name,
            last_name=application.candidate.last_name,
            personal_email=application.candidate.email,
            onboarding_type=onboarding_type,
            position=application.job_posting.title,
            department=application.job_posting.department,
            start_date=start_date,
            salary=salary,
            admin_notes=f"Created from hiring application #{application.id}",
        )

        # Link application to onboarding record
        application.onboarding_record_id = onboarding.id

        # Update application status to hired
        application.change_status(ApplicationStatus.HIRED, user_id=current_user.id)

        flash(_("Congratulations! %(name)s has been hired. Onboarding record created.") % {"name": application.candidate.full_name}, "success")
        return redirect(url_for("people_bp.onboarding_detail", record_id=onboarding.id))

    # GET - show confirmation form
    return render_template(
        "people/desktop/hiring/applications/hire.html",
        active_page="jobs",
        title=f"Hire {application.candidate.full_name}",
        page_icon="fa-solid fa-user-check",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        application=application,
    )


# -----------------------------------------------------------------------------
# Interviews
# -----------------------------------------------------------------------------


@blueprint.route("/hiring/interviews")
@login_required
@admin_required
def hiring_interviews():
    """List upcoming and recent interviews"""
    upcoming = Interview.get_upcoming(limit=20)

    # Get recent completed interviews
    recent = Interview.scoped().options(
        joinedload(Interview.application).joinedload(Application.candidate),
        joinedload(Interview.application).joinedload(Application.job_posting),
        joinedload(Interview.interviewer),
    ).filter(
        Interview.status.in_([InterviewStatus.COMPLETED, InterviewStatus.CANCELLED, InterviewStatus.NO_SHOW])
    ).order_by(Interview.scheduled_at.desc()).limit(10).all()

    # Use mobile-optimized template on mobile
    if is_mobile():
        return render_device_template(
            "people/desktop/hiring/interviews.html",
            active_page="interviews",
            title="Interviews",
            page_icon="fa-solid fa-calendar",
            icon_color=g.workspace_color,
            module_home="people_bp.hiring_index",
            upcoming=upcoming,
            recent=recent,
            InterviewStatus=InterviewStatus,
        )

    return render_template(
        "people/desktop/hiring/interviews/index.html",
        active_page="interviews",
        title="Interviews",
        page_icon="fa-solid fa-calendar",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        upcoming=upcoming,
        recent=recent,
        InterviewStatus=InterviewStatus,
    )


@blueprint.route("/hiring/applications/<int:application_id>/interviews/new", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_interview_schedule(application_id):
    """Schedule a new interview for an application"""
    application = Application.get_by_id(application_id)
    if not application:
        flash(_("Application not found"), "error")
        return redirect(url_for("people_bp.hiring_jobs"))

    if request.method == "POST":
        # Parse the scheduled datetime
        scheduled_date = request.form.get("scheduled_date")
        scheduled_time = request.form.get("scheduled_time")

        try:
            scheduled_at = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            flash(_("Invalid date/time format"), "error")
            return redirect(url_for("people_bp.hiring_interview_schedule", application_id=application_id))

        # Get interviewer if specified
        interviewer_id = request.form.get("interviewer_id")

        interview = Interview(
            application_id=application.id,
            interview_type=InterviewType[request.form.get("interview_type", "VIDEO")],
            scheduled_at=scheduled_at,
            duration_minutes=int(request.form.get("duration", 60)),
            location=request.form.get("location") or None,
            interviewer_id=int(interviewer_id) if interviewer_id else None,
        )

        db.session.add(interview)

        # Log activity
        ApplicationActivity.log(
            application_id=application.id,
            activity_type=ActivityType.INTERVIEW_SCHEDULED,
            description=f"{interview.interview_type.value} scheduled for {scheduled_at.strftime('%b %d at %I:%M %p')}",
            user_id=current_user.id,
        )

        db.session.commit()

        # Update application status to Interviewing if it's in an earlier stage
        if application.status in [ApplicationStatus.NEW, ApplicationStatus.SCREENING]:
            application.change_status(ApplicationStatus.INTERVIEWING, user_id=current_user.id)

        flash(_("Interview scheduled successfully!"), "success")
        return redirect(url_for("people_bp.hiring_application_detail", application_id=application_id))

    # Get employees for interviewer dropdown
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus
    employees = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()

    return render_template(
        "people/desktop/hiring/interviews/form.html",
        active_page="jobs",
        title="Schedule Interview",
        page_icon="fa-solid fa-calendar-plus",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        application=application,
        interview=None,
        employees=employees,
        InterviewType=InterviewType,
    )


@blueprint.route("/hiring/interviews/<int:interview_id>/complete", methods=["GET", "POST"])
@login_required
@admin_required
def hiring_interview_complete(interview_id):
    """Complete an interview with feedback"""
    interview = Interview.get_by_id(interview_id)
    if not interview:
        flash(_("Interview not found"), "error")
        return redirect(url_for("people_bp.hiring_interviews"))

    if request.method == "POST":
        feedback = request.form.get("feedback", "").strip()
        recommendation = request.form.get("recommendation")

        rec_enum = None
        if recommendation:
            try:
                rec_enum = InterviewRecommendation[recommendation]
            except KeyError:
                pass

        interview.complete(feedback=feedback, recommendation=rec_enum, user_id=current_user.id)

        flash(_("Interview feedback saved!"), "success")
        return redirect(url_for("people_bp.hiring_application_detail", application_id=interview.application_id))

    return render_template(
        "people/desktop/hiring/interviews/complete.html",
        active_page="interviews",
        title="Complete Interview",
        page_icon="fa-solid fa-calendar-check",
        icon_color=g.workspace_color,
        module_home="people_bp.hiring_index",
        interview=interview,
        InterviewRecommendation=InterviewRecommendation,
    )


@blueprint.route("/hiring/interviews/<int:interview_id>/cancel", methods=["POST"])
@login_required
@admin_required
def hiring_interview_cancel(interview_id):
    """Cancel an interview"""
    interview = Interview.get_by_id(interview_id)
    if not interview:
        flash(_("Interview not found"), "error")
        return redirect(url_for("people_bp.hiring_interviews"))

    interview.cancel(user_id=current_user.id)
    flash(_("Interview cancelled"), "success")

    return redirect(request.referrer or url_for("people_bp.hiring_application_detail", application_id=interview.application_id))
