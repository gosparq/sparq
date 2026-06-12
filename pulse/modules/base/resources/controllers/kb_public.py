# -----------------------------------------------------------------------------
# sparQ - Resources Module - Public Knowledge Base Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import uuid

from flask import Blueprint, abort, redirect, render_template, request, session, url_for
from flask_login import current_user

from system.device.template import render_device_template

from ..models.kb_article import KBArticle
from ..models.kb_category import KBCategory
from ..models.kb_feedback import KBFeedback
from ..models.kb_subcategory import KBSubcategory

kb_blueprint = Blueprint(
    "kb_bp",
    __name__,
    template_folder="../views/templates",
)


def get_session_id() -> str:
    """Get or create a session ID for anonymous feedback tracking."""
    if "kb_session_id" not in session:
        session["kb_session_id"] = str(uuid.uuid4())
    return session["kb_session_id"]


def can_view_article(article: KBArticle) -> bool:
    """Check if current user can view an article."""
    if article.is_public:
        return True
    return current_user.is_authenticated


@kb_blueprint.route("/")
def index():
    """Public KB home - list all categories with public articles."""
    categories = KBCategory.get_all(active_only=True)

    # Filter to categories with public articles (or any if logged in)
    visible_categories = []
    for cat in categories:
        if current_user.is_authenticated:
            if cat.article_count > 0:
                visible_categories.append(cat)
        else:
            if cat.public_article_count > 0:
                visible_categories.append(cat)

    return render_device_template(
        "resources/desktop/kb_public/index.html",
        categories=visible_categories,
        is_authenticated=current_user.is_authenticated,
    )


@kb_blueprint.route("/search")
def search():
    """Search public articles."""
    query = request.args.get("q", "").strip()

    if not query:
        return redirect(url_for("kb_bp.index"))

    include_private = current_user.is_authenticated
    results = KBArticle.search(query, include_private=include_private, limit=50)

    return render_device_template(
        "resources/desktop/kb_public/search.html",
        query=query,
        results=results,
        is_authenticated=current_user.is_authenticated,
    )


@kb_blueprint.route("/<category_slug>")
def category(category_slug: str):
    """Category page - shows subcategories and direct articles."""
    cat = KBCategory.get_by_slug(category_slug)
    if not cat:
        abort(404)

    include_private = current_user.is_authenticated

    # Get subcategories
    subcategories = KBSubcategory.get_by_category(cat.id, active_only=True)

    # Filter subcategories to those with visible articles
    visible_subcategories = []
    for sub in subcategories:
        if include_private:
            if sub.article_count > 0:
                visible_subcategories.append(sub)
        else:
            if sub.public_article_count > 0:
                visible_subcategories.append(sub)

    # Get direct articles (not in subcategory)
    articles = KBArticle.get_by_category(cat.id, include_private=include_private)

    return render_device_template(
        "resources/desktop/kb_public/category.html",
        category=cat,
        subcategories=visible_subcategories,
        articles=articles,
        is_authenticated=current_user.is_authenticated,
    )


@kb_blueprint.route("/<category_slug>/<path_part>")
def category_or_article(category_slug: str, path_part: str):
    """Handle both subcategory and direct article URLs."""
    cat = KBCategory.get_by_slug(category_slug)
    if not cat:
        abort(404)

    # First, check if it's a subcategory
    subcategory = KBSubcategory.get_by_slug(cat.id, path_part)
    if subcategory:
        # It's a subcategory - show subcategory page
        include_private = current_user.is_authenticated
        articles = KBArticle.get_by_subcategory(subcategory.id, include_private=include_private)

        return render_device_template(
            "resources/desktop/kb_public/subcategory.html",
            category=cat,
            subcategory=subcategory,
            articles=articles,
            is_authenticated=current_user.is_authenticated,
        )

    # Not a subcategory - check if it's an article directly under category
    article = KBArticle.get_by_slug(category_slug, path_part, subcategory_slug=None)
    if article and can_view_article(article):
        article.increment_view_count()

        # Check if user has already submitted feedback
        user_id = current_user.id if current_user.is_authenticated else None
        session_id = get_session_id()
        has_feedback = KBFeedback.has_submitted(article.id, user_id, session_id)

        return render_device_template(
            "resources/desktop/kb_public/article.html",
            article=article,
            has_feedback=has_feedback,
            is_authenticated=current_user.is_authenticated,
        )

    abort(404)


@kb_blueprint.route("/<category_slug>/<subcategory_slug>/<article_slug>")
def article(category_slug: str, subcategory_slug: str, article_slug: str):
    """Article page with subcategory."""
    article = KBArticle.get_by_slug(category_slug, article_slug, subcategory_slug)

    if not article or not can_view_article(article):
        abort(404)

    article.increment_view_count()

    # Check if user has already submitted feedback
    user_id = current_user.id if current_user.is_authenticated else None
    session_id = get_session_id()
    has_feedback = KBFeedback.has_submitted(article.id, user_id, session_id)

    return render_device_template(
        "resources/desktop/kb_public/article.html",
        article=article,
        has_feedback=has_feedback,
        is_authenticated=current_user.is_authenticated,
    )


@kb_blueprint.route("/feedback/<int:article_id>", methods=["POST"])
def submit_feedback(article_id: int):
    """Submit feedback for an article."""
    article = KBArticle.get_by_id(article_id)
    if not article:
        abort(404)

    if not can_view_article(article):
        abort(403)

    is_helpful = request.form.get("helpful") == "yes"
    comment = request.form.get("comment", "").strip() or None

    user_id = current_user.id if current_user.is_authenticated else None
    session_id = get_session_id()

    feedback = KBFeedback.submit(
        article_id=article_id,
        is_helpful=is_helpful,
        user_id=user_id,
        session_id=session_id,
        comment=comment,
    )

    # Return the "thank you" partial for HTMX
    return render_template(
        "resources/desktop/kb_public/_feedback_thanks.html",
        submitted=feedback is not None,
    )
