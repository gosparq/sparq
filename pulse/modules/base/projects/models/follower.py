# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# Licensed under the GNU Affero General Public License v3.0 — see LICENSE

"""project_follower association table — links WorkspaceUser to Project as an interested party."""

from system.db.database import db
from system.db.decorators import ModelRegistry

project_follower = db.Table(
    "project_follower",
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
    db.UniqueConstraint("project_id", "member_id", name="uq_project_follower"),
    db.Index("ix_project_follower_project_id", "project_id"),
    db.Index("ix_project_follower_member_id", "member_id"),
)

ModelRegistry.register_table(project_follower, "projects")
