# -----------------------------------------------------------------------------
# sparQ - Resources Module - Knowledge Controller (Admin)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Admin-only KB management: Create, edit, delete articles/categories.
Staff browsing view is in kb_staff.py (read-only access to all articles).
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from system.auth.decorators import admin_required
from system.i18n.translation import translate as _

from ..models.kb_article import KBArticle
from ..models.kb_category import KBCategory
from ..models.kb_feedback import KBFeedback
from ..models.kb_subcategory import KBSubcategory

knowledge_blueprint = Blueprint(
    "knowledge_blueprint",
    __name__,
    template_folder="../views/templates",
)


@knowledge_blueprint.route("/")
@login_required
@admin_required
def index():
    """Knowledge base admin dashboard."""
    categories = KBCategory.get_all(active_only=False)
    articles = KBArticle.get_recent(limit=10, include_private=True)
    recent_feedback = KBFeedback.get_recent_feedback(limit=10)

    # Stats
    total_articles = KBArticle.scoped().filter_by(is_active=True).count()
    public_articles = KBArticle.scoped().filter_by(is_active=True, is_public=True).count()
    total_categories = KBCategory.scoped().filter_by(is_active=True).count()
    total_feedback = KBFeedback.scoped().count()

    return render_template(
        "resources/desktop/kb_admin/index.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        categories=categories,
        articles=articles,
        recent_feedback=recent_feedback,
        stats={
            "total_articles": total_articles,
            "public_articles": public_articles,
            "private_articles": total_articles - public_articles,
            "total_categories": total_categories,
            "total_feedback": total_feedback,
        },
    )


# -----------------------------------------------------------------------------
# Article Routes
# -----------------------------------------------------------------------------


@knowledge_blueprint.route("/articles")
@login_required
@admin_required
def articles_list():
    """List all articles."""
    category_id = request.args.get("category", type=int)
    status = request.args.get("status", "all")
    visibility = request.args.get("visibility", "all")
    search_query = request.args.get("q", "").strip()

    # If searching, use the search method
    if search_query:
        articles = KBArticle.search(search_query, include_private=True, limit=100)
        # Apply additional filters to search results
        if category_id:
            articles = [a for a in articles if a.category_id == category_id]
        if status == "active":
            articles = [a for a in articles if a.is_active]
        elif status == "inactive":
            articles = [a for a in articles if not a.is_active]
        if visibility == "public":
            articles = [a for a in articles if a.is_public]
        elif visibility == "private":
            articles = [a for a in articles if not a.is_public]
    else:
        query = KBArticle.scoped()

        if category_id:
            query = query.filter_by(category_id=category_id)
        if status == "active":
            query = query.filter_by(is_active=True)
        elif status == "inactive":
            query = query.filter_by(is_active=False)
        if visibility == "public":
            query = query.filter_by(is_public=True)
        elif visibility == "private":
            query = query.filter_by(is_public=False)

        articles = query.order_by(KBArticle.updated_at.desc()).all()

    categories = KBCategory.get_all(active_only=False)

    return render_template(
        "resources/desktop/kb_admin/articles/index.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        articles=articles,
        categories=categories,
        filters={
            "category": category_id,
            "status": status,
            "visibility": visibility,
            "q": search_query,
        },
    )


@knowledge_blueprint.route("/articles/new", methods=["GET", "POST"])
@login_required
@admin_required
def article_new():
    """Create a new article."""
    categories = KBCategory.get_all(active_only=True)

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        subcategory_id = request.form.get("subcategory_id", type=int) or None
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        excerpt = request.form.get("excerpt", "").strip() or None
        is_public = request.form.get("is_public") == "on"

        if not category_id:
            flash(_("Please select a category."), "error")
        elif not title:
            flash(_("Please enter a title."), "error")
        elif not content:
            flash(_("Please enter content."), "error")
        else:
            article = KBArticle.create(
                category_id=category_id,
                subcategory_id=subcategory_id,
                title=title,
                content=content,
                excerpt=excerpt,
                is_public=is_public,
            )
            flash(_("Article created successfully."), "success")
            return redirect(url_for("knowledge_blueprint.article_detail", article_id=article.id))

    # Get subcategories for first category (will be updated via HTMX)
    subcategories = []
    if categories:
        subcategories = KBSubcategory.get_by_category(categories[0].id)

    return render_template(
        "resources/desktop/kb_admin/articles/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        article=None,
        categories=categories,
        subcategories=subcategories,
    )


@knowledge_blueprint.route("/articles/<int:article_id>")
@login_required
@admin_required
def article_detail(article_id: int):
    """View article detail with feedback stats."""
    article = KBArticle.get_by_id(article_id)
    if not article:
        flash(_("Article not found."), "error")
        return redirect(url_for("knowledge_blueprint.articles_list"))

    feedback_stats = KBFeedback.get_stats(article_id)
    feedback_list = KBFeedback.get_by_article(article_id)

    return render_template(
        "resources/desktop/kb_admin/articles/detail.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        article=article,
        feedback_stats=feedback_stats,
        feedback_list=feedback_list,
    )


@knowledge_blueprint.route("/articles/<int:article_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def article_edit(article_id: int):
    """Edit an article."""
    article = KBArticle.get_by_id(article_id)
    if not article:
        flash(_("Article not found."), "error")
        return redirect(url_for("knowledge_blueprint.articles_list"))

    categories = KBCategory.get_all(active_only=False)

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        subcategory_id = request.form.get("subcategory_id", type=int) or None
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()
        excerpt = request.form.get("excerpt", "").strip() or None
        is_public = request.form.get("is_public") == "on"
        is_active = request.form.get("is_active") == "on"

        if not category_id:
            flash(_("Please select a category."), "error")
        elif not title:
            flash(_("Please enter a title."), "error")
        elif not content:
            flash(_("Please enter content."), "error")
        else:
            article.update(
                category_id=category_id,
                subcategory_id=subcategory_id if subcategory_id else 0,
                title=title,
                content=content,
                excerpt=excerpt,
                is_public=is_public,
                is_active=is_active,
            )
            flash(_("Article updated successfully."), "success")
            return redirect(url_for("knowledge_blueprint.article_detail", article_id=article.id))

    subcategories = KBSubcategory.get_by_category(article.category_id, active_only=False)

    return render_template(
        "resources/desktop/kb_admin/articles/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        article=article,
        categories=categories,
        subcategories=subcategories,
    )


@knowledge_blueprint.route("/articles/<int:article_id>/delete", methods=["POST"])
@login_required
@admin_required
def article_delete(article_id: int):
    """Delete an article."""
    article = KBArticle.get_by_id(article_id)
    if not article:
        flash(_("Article not found."), "error")
    else:
        article.delete()
        flash(_("Article deleted successfully."), "success")

    return redirect(url_for("knowledge_blueprint.articles_list"))


# -----------------------------------------------------------------------------
# Category Routes
# -----------------------------------------------------------------------------


@knowledge_blueprint.route("/categories")
@login_required
@admin_required
def categories_list():
    """List all categories and subcategories."""
    categories = KBCategory.get_all(active_only=False)

    return render_template(
        "resources/desktop/kb_admin/categories/index.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        categories=categories,
    )


@knowledge_blueprint.route("/categories/new", methods=["GET", "POST"])
@login_required
@admin_required
def category_new():
    """Create a new category."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        icon_class = request.form.get("icon_class", "").strip() or None

        if not name:
            flash(_("Please enter a name."), "error")
        else:
            KBCategory.create(
                name=name,
                description=description,
                icon_class=icon_class,
            )
            flash(_("Category created successfully."), "success")
            return redirect(url_for("knowledge_blueprint.categories_list"))

    return render_template(
        "resources/desktop/kb_admin/categories/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        category=None,
    )


@knowledge_blueprint.route("/categories/<int:category_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def category_edit(category_id: int):
    """Edit a category."""
    category = KBCategory.get_by_id(category_id)
    if not category:
        flash(_("Category not found."), "error")
        return redirect(url_for("knowledge_blueprint.categories_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        icon_class = request.form.get("icon_class", "").strip() or None
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash(_("Please enter a name."), "error")
        else:
            category.update(
                name=name,
                description=description,
                icon_class=icon_class,
                is_active=is_active,
            )
            flash(_("Category updated successfully."), "success")
            return redirect(url_for("knowledge_blueprint.categories_list"))

    return render_template(
        "resources/desktop/kb_admin/categories/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        category=category,
    )


@knowledge_blueprint.route("/categories/<int:category_id>/delete", methods=["POST"])
@login_required
@admin_required
def category_delete(category_id: int):
    """Delete a category."""
    category = KBCategory.get_by_id(category_id)
    if not category:
        flash(_("Category not found."), "error")
    elif not category.delete():
        flash(_("Cannot delete category with articles. Please move or delete articles first."), "error")
    else:
        flash(_("Category deleted successfully."), "success")

    return redirect(url_for("knowledge_blueprint.categories_list"))


# -----------------------------------------------------------------------------
# Subcategory Routes
# -----------------------------------------------------------------------------


@knowledge_blueprint.route("/subcategories/new", methods=["GET", "POST"])
@login_required
@admin_required
def subcategory_new():
    """Create a new subcategory."""
    categories = KBCategory.get_all(active_only=True)
    category_id = request.args.get("category_id", type=int)

    if request.method == "POST":
        category_id = request.form.get("category_id", type=int)
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None

        if not category_id:
            flash(_("Please select a category."), "error")
        elif not name:
            flash(_("Please enter a name."), "error")
        else:
            KBSubcategory.create(
                category_id=category_id,
                name=name,
                description=description,
            )
            flash(_("Subcategory created successfully."), "success")
            return redirect(url_for("knowledge_blueprint.categories_list"))

    return render_template(
        "resources/desktop/kb_admin/subcategories/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        subcategory=None,
        categories=categories,
        selected_category_id=category_id,
    )


@knowledge_blueprint.route("/subcategories/<int:subcategory_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def subcategory_edit(subcategory_id: int):
    """Edit a subcategory."""
    subcategory = KBSubcategory.get_by_id(subcategory_id)
    if not subcategory:
        flash(_("Subcategory not found."), "error")
        return redirect(url_for("knowledge_blueprint.categories_list"))

    categories = KBCategory.get_all(active_only=False)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash(_("Please enter a name."), "error")
        else:
            subcategory.update(
                name=name,
                description=description,
                is_active=is_active,
            )
            flash(_("Subcategory updated successfully."), "success")
            return redirect(url_for("knowledge_blueprint.categories_list"))

    return render_template(
        "resources/desktop/kb_admin/subcategories/form.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        subcategory=subcategory,
        categories=categories,
        selected_category_id=subcategory.category_id,
    )


@knowledge_blueprint.route("/subcategories/<int:subcategory_id>/delete", methods=["POST"])
@login_required
@admin_required
def subcategory_delete(subcategory_id: int):
    """Delete a subcategory."""
    subcategory = KBSubcategory.get_by_id(subcategory_id)
    if not subcategory:
        flash(_("Subcategory not found."), "error")
    elif not subcategory.delete():
        flash(_("Cannot delete subcategory with articles. Please move or delete articles first."), "error")
    else:
        flash(_("Subcategory deleted successfully."), "success")

    return redirect(url_for("knowledge_blueprint.categories_list"))


# -----------------------------------------------------------------------------
# HTMX Partials
# -----------------------------------------------------------------------------


@knowledge_blueprint.route("/subcategories-for-category/<int:category_id>")
@login_required
@admin_required
def subcategories_for_category(category_id: int):
    """Get subcategories for a category (HTMX)."""
    subcategories = KBSubcategory.get_by_category(category_id, active_only=True)
    selected_id = request.args.get("selected", type=int)

    return render_template(
        "resources/desktop/kb_admin/partials/_subcategory_options.html",
        subcategories=subcategories,
        selected_id=selected_id,
    )


@knowledge_blueprint.route("/feedback")
@login_required
@admin_required
def feedback_list():
    """View all feedback."""
    feedback = KBFeedback.get_recent_feedback(limit=100)
    attention_needed = KBFeedback.get_articles_needing_attention()

    return render_template(
        "resources/desktop/kb_admin/feedback/index.html",
        active_page="resources",
        module_home="knowledge_blueprint.index",
        feedback=feedback,
        attention_needed=attention_needed,
    )
