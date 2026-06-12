# -----------------------------------------------------------------------------
# sparQ - Contact AI Tools
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
AI tools for contact operations.

These tools are registered with the AI system and can be called by the LLM
to create, update, or search contacts.
"""

from typing import Any

from system.ai import Tool

from ..models.contact import Contact, ContactType


def _execute_create_contact(args: dict[str, Any]) -> dict[str, Any]:
    """Execute create_contact tool."""
    # Handle first_name/last_name or full_name
    first_name = args.get("first_name")
    last_name = args.get("last_name")

    if not first_name and not last_name:
        full_name = args.get("full_name", "")
        if full_name:
            parts = full_name.strip().split(maxsplit=1)
            first_name = parts[0] if parts else None
            last_name = parts[1] if len(parts) > 1 else None

    # Check for existing contact by phone or email (dedupe)
    phone = args.get("phone")
    email = args.get("email")

    existing = None
    if phone:
        existing = Contact.scoped().filter_by(phone=phone).first()
    if not existing and email:
        existing = Contact.scoped().filter_by(email=email).first()

    if existing:
        # Return info about existing contact for dedupe handling
        return {
            "status": "duplicate",
            "existing_contact_id": existing.id,
            "existing_contact_name": existing.display_name,
            "message": f"Contact with this {'phone' if phone else 'email'} already exists: {existing.display_name}",
        }

    # Create the contact
    contact = Contact.create(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        email=email,
        company_name=args.get("company_name"),
        notes=args.get("notes"),
        is_company=args.get("is_company", False),
        contact_type=ContactType.PROSPECT,  # Default for AI-created contacts
    )

    return {
        "status": "created",
        "contact_id": contact.id,
        "contact_name": contact.display_name,
        "message": f"Created contact: {contact.display_name}",
    }


def _execute_update_contact(args: dict[str, Any]) -> dict[str, Any]:
    """Execute update_contact tool."""
    contact_id = args.get("contact_id")
    if not contact_id:
        return {"status": "error", "message": "contact_id is required"}

    contact = Contact.scoped().filter_by(id=contact_id).first()
    if not contact:
        return {"status": "error", "message": f"Contact {contact_id} not found"}

    # Build update kwargs
    update_fields = {}
    for field in ["first_name", "last_name", "phone", "email", "company_name"]:
        if field in args and args[field]:
            update_fields[field] = args[field]

    # Handle notes specially - append rather than replace
    if "notes" in args and args["notes"]:
        new_notes = args["notes"]
        if contact.notes:
            update_fields["notes"] = f"{contact.notes}\n\n{new_notes}"
        else:
            update_fields["notes"] = new_notes

    if update_fields:
        contact.update(**update_fields)

    return {
        "status": "updated",
        "contact_id": contact.id,
        "contact_name": contact.display_name,
        "message": f"Updated contact: {contact.display_name}",
    }


def _execute_search_contacts(args: dict[str, Any]) -> dict[str, Any]:
    """Execute search_contacts tool."""
    query = args.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "Search query is required"}

    # Use Contact.search method
    results = Contact.search(query)

    contacts = [
        {
            "id": c.id,
            "name": c.display_name,
            "phone": c.phone,
            "email": c.email,
            "company": c.company_name,
        }
        for c in results[:10]  # Limit to 10 results
    ]

    return {
        "status": "success",
        "count": len(contacts),
        "contacts": contacts,
        "message": f"Found {len(contacts)} contact(s) matching '{query}'",
    }


# Tool definitions

create_contact = Tool(
    name="create_contact",
    description="Create a new contact (person or company). Use this when the user provides information about someone they met or want to add to the system.",
    parameters={
        "type": "object",
        "properties": {
            "first_name": {
                "type": "string",
                "description": "First name of the contact",
            },
            "last_name": {
                "type": "string",
                "description": "Last name of the contact",
            },
            "full_name": {
                "type": "string",
                "description": "Full name if first/last not separated",
            },
            "phone": {
                "type": "string",
                "description": "Phone number",
            },
            "email": {
                "type": "string",
                "description": "Email address",
            },
            "company_name": {
                "type": "string",
                "description": "Company or organization name",
            },
            "notes": {
                "type": "string",
                "description": "Additional notes about the contact (interests, how you met, connections, etc.)",
            },
            "is_company": {
                "type": "boolean",
                "description": "True if this is a company contact rather than a person",
                "default": False,
            },
        },
        "required": [],
    },
    execute=_execute_create_contact,
)

update_contact = Tool(
    name="update_contact",
    description="Update an existing contact's information. Use this when the user wants to modify or add information to an existing contact.",
    parameters={
        "type": "object",
        "properties": {
            "contact_id": {
                "type": "integer",
                "description": "ID of the contact to update",
            },
            "first_name": {
                "type": "string",
                "description": "New first name",
            },
            "last_name": {
                "type": "string",
                "description": "New last name",
            },
            "phone": {
                "type": "string",
                "description": "New phone number",
            },
            "email": {
                "type": "string",
                "description": "New email address",
            },
            "company_name": {
                "type": "string",
                "description": "New company name",
            },
            "notes": {
                "type": "string",
                "description": "Additional notes to append to existing notes",
            },
        },
        "required": ["contact_id"],
    },
    execute=_execute_update_contact,
)

search_contacts = Tool(
    name="search_contacts",
    description="Search for existing contacts by name, phone, or email. Use this to find contacts before creating duplicates or when the user asks to find someone.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (name, phone number, or email)",
            },
        },
        "required": ["query"],
    },
    execute=_execute_search_contacts,
)
