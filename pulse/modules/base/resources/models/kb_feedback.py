# -----------------------------------------------------------------------------
# sparQ - Knowledge Base Feedback Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class KBFeedback(db.Model, WorkspaceMixin):
    """Feedback on knowledge base articles (staff-only visible)."""

    __tablename__ = "kb_feedback"

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(
        db.Integer,
        db.ForeignKey("kb_article.id", ondelete="CASCADE"),
        nullable=False,
    )
    is_helpful = db.Column(db.Boolean, nullable=False)
    comment = db.Column(db.Text)

    # Track who submitted (nullable for anonymous public feedback)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    session_id = db.Column(db.String(100))  # For anonymous tracking

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Index for efficient duplicate checking
    __table_args__ = (
        db.Index("ix_kb_feedback_article_session", "article_id", "session_id"),
    )

    @classmethod
    def get_by_article(cls, article_id: int) -> list["KBFeedback"]:
        """Get all feedback for an article."""
        return (
            cls.scoped().filter_by(article_id=article_id)
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def has_submitted(
        cls,
        article_id: int,
        user_id: int | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Check if user/session has already submitted feedback."""
        if user_id:
            return cls.scoped().filter_by(article_id=article_id, user_id=user_id).first() is not None
        if session_id:
            return cls.scoped().filter_by(article_id=article_id, session_id=session_id).first() is not None
        return False

    @classmethod
    def submit(
        cls,
        article_id: int,
        is_helpful: bool,
        user_id: int | None = None,
        session_id: str | None = None,
        comment: str | None = None,
    ) -> "KBFeedback | None":
        """Submit feedback. Returns None if duplicate."""
        # Check for duplicate
        if cls.has_submitted(article_id, user_id, session_id):
            return None

        feedback = cls(
            article_id=article_id,
            is_helpful=is_helpful,
            user_id=user_id,
            session_id=session_id,
            comment=comment,
        )
        db.session.add(feedback)
        db.session.commit()
        return feedback

    @classmethod
    def get_stats(cls, article_id: int) -> dict:
        """Get feedback stats for an article."""
        helpful = cls.scoped().filter_by(article_id=article_id, is_helpful=True).count()
        not_helpful = cls.scoped().filter_by(article_id=article_id, is_helpful=False).count()
        total = helpful + not_helpful
        return {
            "helpful": helpful,
            "not_helpful": not_helpful,
            "total": total,
            "helpful_percent": round((helpful / total) * 100) if total > 0 else 0,
        }

    @classmethod
    def get_recent_feedback(cls, limit: int = 20) -> list["KBFeedback"]:
        """Get most recent feedback across all articles."""
        return cls.scoped().order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_articles_needing_attention(cls, threshold: float = 0.5) -> list[dict]:
        """Get articles where less than threshold percent found helpful."""
        from .kb_article import KBArticle

        results = []
        articles = KBArticle.scoped().filter_by(is_active=True).all()

        for article in articles:
            stats = cls.get_stats(article.id)
            if stats["total"] >= 3:  # Need at least 3 votes to be meaningful
                if stats["helpful_percent"] < (threshold * 100):
                    results.append({"article": article, "stats": stats})

        return sorted(results, key=lambda x: x["stats"]["helpful_percent"])
