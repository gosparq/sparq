# -----------------------------------------------------------------------------
# sparQ - Industry Terminology
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------
"""
Industry-specific terminology mapping.

This module provides industry-specific term overrides that are automatically
applied by the translate() function in system/i18n/translation.py.

Developers just use _("Jobs") everywhere - if the current industry has an
override for "Jobs", it will be applied automatically (e.g., "Projects"
for Professional Services).
"""

from flask import g

from modules.base.core.models.workspace_settings import Industry

TERMINOLOGY = {
    Industry.FIELD_SERVICE: {
        "employee": "Team Member",
        "employees": "Team",
        "department": "Service Area",
        "departments": "Service Areas",
        "position": "Role",
        "positions": "Roles",
        "schedule": "Schedule",
        "schedules": "Schedules",
        "team": "Team",
        "teams": "Teams",
        "job": "Job",
        "jobs": "Jobs",
        "Jobs": "Jobs",
        "Job #": "Job #",
        "New Job": "New Job",
        "Search jobs...": "Search jobs...",
        "No jobs found": "No jobs found",
        "Create your first job": "Create your first job",
        "Start Job": "Start Job",
    },
    Industry.PROFESSIONAL_SERVICES: {
        "employee": "Consultant",
        "employees": "Consultants",
        "department": "Practice",
        "departments": "Practices",
        "position": "Title",
        "positions": "Titles",
        "team": "Team",
        "teams": "Teams",
        "job": "Project",
        "jobs": "Projects",
        "Job": "Project",
        "Jobs": "Projects",
        "Job #": "Project #",
        "New Job": "New Project",
        "Search jobs...": "Search projects...",
        "No jobs found": "No projects found",
        "Create your first job": "Create your first project",
        "Back to Jobs": "Back to Projects",
        "Job Information": "Project Information",
        "Job Details": "Project Details",
        "Update Status": "Update Status",
        "Schedule Job": "Schedule Project",
        "Start Job": "Start Project",
        "Complete Job": "Complete Project",
        "Cancel Job": "Cancel Project",
        "Delete Job": "Delete Project",
        "Brief summary of the job...": "Brief summary of the project...",
    },
    Industry.WORKFORCE: {
        "employee": "Person",
        "employees": "People",
        "department": "Department",
        "departments": "Departments",
        "position": "Position",
        "positions": "Positions",
        "schedule": "Schedule",
        "schedules": "Schedules",
        "team": "Team",
        "teams": "Teams",
        "job": "Job",
        "jobs": "Jobs",
        "Jobs": "Jobs",
        "Job #": "Job #",
        "New Job": "New Job",
        "Search jobs...": "Search jobs...",
        "No jobs found": "No jobs found",
        "Create your first job": "Create your first job",
        "Start Job": "Start Job",
    },
}


def get_industry_term(key: str) -> str:
    """
    Get industry-specific term for a key.
    Returns original key if no industry term exists.

    This is called internally by translate() - developers should just use _().

    Args:
        key: The base term key (e.g., "employee", "Jobs")

    Returns:
        The industry-specific term, or the original key if not found
    """
    try:
        industry = g.company_settings.industry or Industry.WORKFORCE
        terms = TERMINOLOGY.get(industry, TERMINOLOGY[Industry.WORKFORCE])
        return terms.get(key, key)  # Return original key unchanged
    except (AttributeError, RuntimeError):
        # Outside request context or no company settings
        return key
