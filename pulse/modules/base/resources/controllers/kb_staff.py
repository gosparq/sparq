# -----------------------------------------------------------------------------
# sparQ - Resources Module - Staff Knowledge Base Browser
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Staff-only KB browsing view. Shows ALL articles (public + private) to
authenticated staff members. Read-only - no CRUD operations.
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import login_required

from ..models.kb_article import KBArticle
from ..models.kb_category import KBCategory
from ..models.kb_subcategory import KBSubcategory

kb_staff_blueprint = Blueprint(
    "kb_staff_bp",
    __name__,
    template_folder="../views/templates",
)


@kb_staff_blueprint.route("/")
@login_required
def index():
    """Staff KB home - list all categories with article counts."""
    categories = KBCategory.get_all(active_only=True)

    # Show all categories that have articles (public or private)
    visible_categories = [cat for cat in categories if cat.article_count > 0]

    return render_template(
        "resources/desktop/kb_admin/browse/index.html",
        active_page="resources",
        module_home="kb_staff_bp.index",
        categories=visible_categories,
    )


@kb_staff_blueprint.route("/search")
@login_required
def search():
    """Search all articles (public + private)."""
    query = request.args.get("q", "").strip()

    if not query:
        return redirect(url_for("kb_staff_bp.index"))

    # Staff can see all articles
    results = KBArticle.search(query, include_private=True, limit=50)

    return render_template(
        "resources/desktop/kb_admin/browse/search.html",
        active_page="resources",
        module_home="kb_staff_bp.index",
        query=query,
        results=results,
    )


@kb_staff_blueprint.route("/<category_slug>")
@login_required
def category(category_slug: str):
    """Category page - shows all subcategories and direct articles."""
    cat = KBCategory.get_by_slug(category_slug)
    if not cat:
        abort(404)

    # Get all subcategories with articles
    subcategories = KBSubcategory.get_by_category(cat.id, active_only=True)
    visible_subcategories = [sub for sub in subcategories if sub.article_count > 0]

    # Get direct articles (not in subcategory) - include private
    articles = KBArticle.get_by_category(cat.id, include_private=True)

    return render_template(
        "resources/desktop/kb_admin/browse/category.html",
        active_page="resources",
        module_home="kb_staff_bp.index",
        category=cat,
        subcategories=visible_subcategories,
        articles=articles,
    )


@kb_staff_blueprint.route("/<category_slug>/<path_part>")
@login_required
def category_or_article(category_slug: str, path_part: str):
    """Handle both subcategory and direct article URLs."""
    cat = KBCategory.get_by_slug(category_slug)
    if not cat:
        abort(404)

    # First, check if it's a subcategory
    subcategory = KBSubcategory.get_by_slug(cat.id, path_part)
    if subcategory:
        # It's a subcategory - show subcategory page
        articles = KBArticle.get_by_subcategory(subcategory.id, include_private=True)

        return render_template(
            "resources/desktop/kb_admin/browse/subcategory.html",
            active_page="resources",
            module_home="kb_staff_bp.index",
            category=cat,
            subcategory=subcategory,
            articles=articles,
        )

    # Not a subcategory - check if it's an article directly under category
    article = KBArticle.get_by_slug(category_slug, path_part, subcategory_slug=None)
    if article:
        article.increment_view_count()

        return render_template(
            "resources/desktop/kb_admin/browse/article.html",
            active_page="resources",
            module_home="kb_staff_bp.index",
            article=article,
        )

    abort(404)


@kb_staff_blueprint.route("/<category_slug>/<subcategory_slug>/<article_slug>")
@login_required
def article(category_slug: str, subcategory_slug: str, article_slug: str):
    """Article page with subcategory."""
    article = KBArticle.get_by_slug(category_slug, article_slug, subcategory_slug)

    if not article:
        abort(404)

    article.increment_view_count()

    return render_template(
        "resources/desktop/kb_admin/browse/article.html",
        active_page="resources",
        module_home="kb_staff_bp.index",
        article=article,
    )
