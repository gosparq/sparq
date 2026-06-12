# -----------------------------------------------------------------------------
# sparQ - AI Routes
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Routes for AI agent actions (confirm, cancel, edit, choose).
"""

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from ..models import AIPendingAction

blueprint = Blueprint(
    "ai_bp",
    __name__,
    template_folder="../views/templates",
)


@blueprint.route("/pending/<int:action_id>/confirm", methods=["POST"])
@login_required
def confirm_action(action_id: int):
    """Confirm and execute a pending action."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Execute the tool
    try:
        from system.ai import ToolRegistry

        # Collect tools
        registry = ToolRegistry()
        current_app.module_loader.pm.hook.register_ai_tools(registry=registry)

        tool = registry.get(action.tool_name)
        if not tool:
            action.mark_failed(f"Tool '{action.tool_name}' not found")
            return render_template("ai/desktop/partials/_receipt.html", action=action, success=False)

        # Execute tool
        result = tool.execute(action.args_json)
        action.mark_executed({"result": str(result)})

        return render_template("ai/desktop/partials/_receipt.html", action=action, success=True, result=result)

    except Exception as e:
        action.mark_failed(str(e))
        return render_template("ai/desktop/partials/_receipt.html", action=action, success=False)


@blueprint.route("/pending/<int:action_id>/cancel", methods=["POST"])
@login_required
def cancel_action(action_id: int):
    """Cancel a pending action."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    action.cancel()
    return render_template("ai/desktop/partials/_receipt.html", action=action, cancelled=True)


@blueprint.route("/pending/<int:action_id>/edit", methods=["GET"])
@login_required
def get_edit_form(action_id: int):
    """Get edit form for a pending action."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    return render_template("ai/desktop/partials/_edit_form.html", action=action)


@blueprint.route("/pending/<int:action_id>/edit", methods=["POST"])
@login_required
def save_edit(action_id: int):
    """Save edits to a pending action."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Update args from form data
    new_args = {}
    for key in request.form:
        if key.startswith("arg_"):
            arg_name = key[4:]  # Remove "arg_" prefix
            new_args[arg_name] = request.form[key]

    action.update_args(new_args)
    return render_template("ai/desktop/partials/_proposal.html", action=action)


@blueprint.route("/pending/<int:action_id>", methods=["GET"])
@login_required
def get_proposal(action_id: int):
    """Get the proposal view for a pending action."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    return render_template("ai/desktop/partials/_proposal.html", action=action)


@blueprint.route("/pending/<int:action_id>/choose", methods=["POST"])
@login_required
def choose_candidate(action_id: int):
    """Choose a candidate for ambiguous reference resolution."""
    action = AIPendingAction.get_by_id(action_id)

    if not action:
        return jsonify({"error": "Action not found"}), 404

    if action.created_by_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json() or {}
    contact_id = data.get("contact_id")

    if not contact_id:
        return jsonify({"error": "contact_id required"}), 400

    # Update clarification with chosen candidate and re-process
    # This will be implemented when we add the full AI service integration
    # For now, just store the choice
    clarification = action.clarification_json or {}
    clarification["chosen_contact_id"] = contact_id
    action.clarification_json = clarification
    action.status = "proposed"  # Reset to proposed for re-rendering

    from system.db.database import db
    db.session.commit()

    return render_template("ai/desktop/partials/_proposal.html", action=action)
