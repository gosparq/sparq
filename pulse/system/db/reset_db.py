# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Database reset utility for development and testing.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

#!/usr/bin/env python
"""
Database Reset Script for sparQ

This script:
1. Drops all existing tables
2. Recreates all tables from models
3. Creates default groups (ALL, ADMIN)

Usage:
    python system/db/reset_db.py
    # or
    make reset

For demo data, run: make demo
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def reset_database():
    """Drop and recreate all database tables. Only default groups exist after this."""
    print("=" * 50)
    print("sparQ Database Reset")
    print("=" * 50)

    # Step 1: Nuke the schema BEFORE importing the app (avoids init_database
    # hooks querying old tables with mismatched columns / circular FKs).
    print("\n[1/4] Dropping all tables...")
    from system.startup.config import configure_app
    from sqlalchemy import create_engine, text

    from flask import Flask
    mini = Flask(__name__)
    configure_app(mini)
    db_url = mini.config["SQLALCHEMY_DATABASE_URI"]

    if db_url.startswith("sqlite"):
        import re
        db_path = re.sub(r"^sqlite:///", "", db_url)
        if os.path.exists(db_path):
            os.remove(db_path)
        print(f"      Removed {db_path}")
    else:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.commit()
        engine.dispose()
        print("      Schema dropped and recreated.")

    # Step 2: Now import the app — init_database will see an empty DB and
    # create all tables cleanly via db.create_all().
    print("[2/4] Creating Flask application (rebuilds all tables)...")
    from app import create_app
    create_app()

    print("[3/4] Database setup complete.")

    print("\n" + "=" * 50)
    print("Database reset complete!")
    print("Run 'make demo' to seed demo data.")
    print("=" * 50)


def delete_all_business_data(preserve_gateway: bool = True) -> None:
    """Delete all business data while preserving admin user and groups.

    Deletes in order to respect foreign key constraints.
    Also removes uploaded files from documents and attachments folders.

    Args:
        preserve_gateway: If True (default), keep email/SMS gateway settings.
            Set to False for a full wipe (e.g. Danger Zone delete).
    """
    from system.db.database import db

    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_settings import WorkspaceSettings

    # Import models - handle missing modules gracefully
    models_to_delete = []

    # Core models (Contact, ServiceLocation)
    try:
        from modules.base.core.models.contact import Contact
        from modules.base.core.models.service_location import ServiceLocation

        models_to_delete.extend([ServiceLocation, Contact])
    except ImportError:
        pass

    # Resources models (documents and attachments)
    try:
        from modules.base.resources.models.attachment_link import AttachmentLink
        from modules.base.resources.models.attachment import Attachment
        from modules.base.resources.models.document import Document
        from modules.base.resources.models.folder import Folder
        from modules.base.resources.services import get_docs_dir, get_attachments_dir

        models_to_delete.extend([AttachmentLink, Attachment, Document, Folder])

        # Delete all files in documents and attachments folders
        for folder_path in [get_docs_dir(), get_attachments_dir()]:
            if os.path.exists(folder_path):
                for filename in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
    except ImportError:
        pass

    # Knowledge Base models (feedback before articles, articles before categories)
    try:
        from modules.base.resources.models.kb_feedback import KBFeedback
        from modules.base.resources.models.kb_article import KBArticle
        from modules.base.resources.models.kb_subcategory import KBSubcategory
        from modules.base.resources.models.kb_category import KBCategory

        models_to_delete.extend([KBFeedback, KBArticle, KBSubcategory, KBCategory])
    except ImportError:
        pass

    # Signature models (audit logs before recipients, recipients before requests)
    try:
        from modules.base.resources.models.signature_audit_log import SignatureAuditLog
        from modules.base.resources.models.signature_recipient import SignatureRecipient
        from modules.base.resources.models.signature_request import SignatureRequest

        models_to_delete.extend([SignatureAuditLog, SignatureRecipient, SignatureRequest])
    except ImportError:
        pass

    # AI models (references channel/chat, delete before Connect)
    try:
        from modules.base.ai.models.pending_action import AIPendingAction

        models_to_delete.append(AIPendingAction)
    except ImportError:
        pass

    # Sync models (reactions/read states before posts, posts before channels)
    try:
        from modules.base.updates.models.channel import UpdateChannel
        from modules.base.updates.models.channel_read_state import UpdateChannelReadState
        from modules.base.updates.models.post import UpdatePost
        from modules.base.updates.models.post_reaction import UpdatePostReaction
        from modules.base.updates.models.dm import (
            DMReaction, DM, DMThread,
        )
        from modules.base.updates.models.event import Event
        from modules.base.updates.models.webhook import UpdateWebhook

        models_to_delete.extend([
            UpdateChannelReadState, UpdatePostReaction, UpdatePost, UpdateChannel,
            DMReaction, DM, DMThread,
            Event, UpdateWebhook,
        ])
    except ImportError:
        pass

    # Time Tracking models
    try:
        from modules.base.presence.models.clock_punch_adjustment import ClockPunchAdjustment
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest
        from modules.base.presence.models.time_entry import TimeEntry
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.leave_request import LeaveRequest
        from modules.base.presence.models.settings import TimeTrackingSettings

        models_to_delete.extend([
            ClockPunchAdjustment, PunchCorrectionRequest, TimeEntry,
            ClockPunch, LeaveRequest, TimeTrackingSettings,
        ])
    except ImportError:
        pass

    # Finance models
    try:
        from modules.base.finance.models.accounting import AccountingLedger, AccountingAccount
        from modules.base.finance.models.expense import Expense

        models_to_delete.extend([AccountingLedger, AccountingAccount, Expense])
    except ImportError:
        pass

    # Notifications
    try:
        from modules.base.core.models.notification import SystemNotification

        models_to_delete.append(SystemNotification)
    except ImportError:
        pass

    # Dashboard models
    try:
        from modules.base.dashboard.models import ActivityLog

        models_to_delete.append(ActivityLog)
    except ImportError:
        pass

    # Hiring models (activities/interviews before applications, applications before jobs/candidates)
    try:
        from modules.base.people.models.hiring.activity import ApplicationActivity
        from modules.base.people.models.hiring.interview import Interview
        from modules.base.people.models.hiring.application import Application
        from modules.base.people.models.hiring.job import JobPosting
        from modules.base.people.models.hiring.candidate import Candidate

        models_to_delete.extend([
            ApplicationActivity, Interview, Application, JobPosting, Candidate,
        ])
    except ImportError:
        pass

    # Team models (offboarding/notes/tax before onboarding before employees due to FK)
    try:
        from modules.base.people.models.offboarding import OffboardingAssignment, OffboardingTask
        from modules.base.people.models.person_note import PersonNote
        from modules.base.people.models.taxform import TaxFormRecord
        from modules.base.people.models.onboarding import (
            OnboardingTaskTemplate, OnboardingTask, OnboardingRecord,
        )
        from modules.base.core.models.workspace_user import WorkspaceUser

        models_to_delete.extend([
            OffboardingAssignment, OffboardingTask, PersonNote, TaxFormRecord,
            OnboardingTaskTemplate, OnboardingTask, OnboardingRecord, WorkspaceUser,
        ])
    except ImportError:
        pass

    # User-scoped models (delete before users)
    try:
        from modules.base.core.models.oauth_connection import OAuthConnection
        from modules.base.core.models.push_subscription import PushSubscription
        from modules.base.core.models.user_setting import UserSetting
        from modules.base.resources.models.drive_connection import DriveConnection

        models_to_delete.extend([OAuthConnection, PushSubscription, UserSetting, DriveConnection])
    except ImportError:
        pass

    # Delete all records from each model (commit each individually so
    # a rollback on one table doesn't undo all previous deletes)
    for model in models_to_delete:
        try:
            model.query.delete()
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Delete all users
    User.query.delete()

    # Reset company settings to defaults
    settings = WorkspaceSettings.get_instance()
    settings.company_name = None
    settings.industry = None
    settings.sidebar_config = None  # Reset sidebar to defaults

    # Reset module settings singletons (auto-recreate with defaults on next access)
    try:
        from modules.base.resources.models.settings import ResourcesSettings

        ResourcesSettings.scoped().delete()
        db.session.commit()
    except (ImportError, Exception):
        db.session.rollback()

    if not preserve_gateway:
        # Clear email settings
        settings.email_provider = None
        settings.email_host = None
        settings.email_port = None
        settings.email_username = None
        settings.email_password = None
        settings.email_from = None
        settings.sms_provider = None

    db.session.commit()


if __name__ == "__main__":
    reset_database()
