# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""project_co_owner association table — links WorkspaceUser to Project as a co-owner."""

from system.db.database import db
from system.db.decorators import ModelRegistry

project_co_owner = db.Table(
    "project_co_owner",
    db.Column(
        "project_id",
        db.Integer,
        db.ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
    ),
    db.Column(
        "member_id",
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="CASCADE"),
        nullable=False,
    ),
    db.UniqueConstraint("project_id", "member_id", name="uq_project_co_owner"),
    db.Index("ix_project_co_owner_project_id", "project_id"),
    db.Index("ix_project_co_owner_member_id", "member_id"),
)

ModelRegistry.register_table(project_co_owner, "projects")
