# -----------------------------------------------------------------------------
# sparQ - Folder Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

from flask_login import current_user

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class Folder(db.Model, WorkspaceMixin, AuditMixin):
    """Folder for organizing documents in the library.

    Lives at the org level (organization_id NOT NULL). `workspace_id` is a
    nullable filter: set = folder belongs to a workspace, NULL = org-wide.
    """

    __tablename__ = "folder"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("folder.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = db.relationship(
        "Folder",
        remote_side=[id],
        backref=db.backref("children", lazy="dynamic"),
        lazy=LAZY,
    )

    __table_args__ = (
        db.UniqueConstraint("parent_id", "name", name="uq_folder_parent_name"),
    )

    @property
    def document_count(self) -> int:
        """Number of documents directly in this folder (excluding subfolders)."""
        return self.documents.count()

    @property
    def path(self) -> str:
        """Full slash-delimited path from the root folder to this folder."""
        parts = [self.name]
        pid = self.parent_id
        while pid:
            ancestor = db.session.get(Folder, pid)
            if not ancestor:
                break
            parts.insert(0, ancestor.name)
            pid = ancestor.parent_id
        return "/" + "/".join(parts)

    @property
    def breadcrumbs(self) -> list["Folder"]:
        """Folders from root → this folder, suitable for breadcrumb rendering."""
        crumbs = [self]
        pid = self.parent_id
        while pid:
            ancestor = db.session.get(Folder, pid)
            if not ancestor:
                break
            crumbs.insert(0, ancestor)
            pid = ancestor.parent_id
        return crumbs

    @classmethod
    def get_by_id(cls, folder_id: int) -> "Folder | None":
        """Get a folder by ID within the active scope."""
        return cls.scoped().filter_by(id=folder_id).first()

    @classmethod
    def get_root_folders(cls) -> list["Folder"]:
        """All folders at the root level (parent_id IS NULL) within the scope."""
        return cls.scoped().filter(cls.parent_id.is_(None)).order_by(cls.name).all()

    @classmethod
    def create(cls, name: str, parent_id: int | None = None) -> "Folder":
        """Create a folder in the active scope.

        workspace_id + organization_id are stamped by before_flush listeners
        (auto_set_workspace_id is skipped in organization scope so org-wide
        folders land with workspace_id=NULL).
        """
        folder = cls(name=name, parent_id=parent_id)
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            folder.created_by_id = current_user.id
        db.session.add(folder)
        db.session.commit()
        return folder

    def rename(self, new_name: str) -> "Folder":
        """Rename this folder; stamps updated_by_id from current_user."""
        self.name = new_name
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
        return self

    def move(self, new_parent_id: int | None) -> "Folder":
        """Move this folder to a different parent (None = root)."""
        self.parent_id = new_parent_id
        if current_user and hasattr(current_user, "id") and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        db.session.commit()
        return self

    def delete(self) -> None:
        """Delete this folder and cascade to its documents and subfolders."""
        db.session.delete(self)
        db.session.commit()
