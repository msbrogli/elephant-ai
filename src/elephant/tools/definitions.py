"""OpenAI function-calling tool schemas for the conversational agent."""

from __future__ import annotations

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_events",
            "description": (
                "Search and list memory events. Use to answer questions about what happened, "
                "find memories by date, person, or topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {
                        "type": "string",
                        "description": "Start date filter (YYYY-MM-DD)",
                    },
                    "date_to": {
                        "type": "string",
                        "description": "End date filter (YYYY-MM-DD)",
                    },
                    "people": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by people involved",
                    },
                    "event_type": {
                        "type": "string",
                        "description": (
                            "Filter by type: milestone, daily, outing, celebration, "
                            "health, travel, mundane, other"
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags",
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text search in title and description",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 20)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event",
            "description": "Get full details of a specific event by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID (e.g. 20260224_park_day)",
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": (
                "Create a new memory event. Use when the user describes something that happened."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the event",
                    },
                    "date": {
                        "type": "string",
                        "description": "Event date (YYYY-MM-DD). Use today if not specified.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Event time (HH:MM) or null",
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "milestone", "daily", "outing", "celebration",
                            "health", "travel", "mundane", "other",
                        ],
                        "description": "Event type",
                    },
                    "description": {
                        "type": "string",
                        "description": "Detailed description of what happened",
                    },
                    "people": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "People involved",
                    },
                    "location": {
                        "type": "string",
                        "description": "Where it happened",
                    },
                    "nostalgia_score": {
                        "type": "number",
                        "description": "0.5-2.0, higher for milestones",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Relevant tags",
                    },
                },
                "required": ["title", "date", "type", "description", "people"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_event",
            "description": "Update fields on an existing event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to update",
                    },
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "people": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "location": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_event",
            "description": "Delete an event by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event ID to delete",
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_context",
            "description": (
                "Read family context: members, friends, locations, notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_context",
            "description": (
                "Update family context. Provide only the fields to add/update."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "family_members": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "role": {"type": "string"},
                                "birthday": {"type": "string"},
                            },
                            "required": ["name", "role"],
                        },
                        "description": "Family members to add/update",
                    },
                    "friends": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "relationship": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                        "description": "Friends to add/update",
                    },
                    "locations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                        "description": "Locations to add/update",
                    },
                    "notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Free-text notes to add",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_people",
            "description": "List all known people in the people directory.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_person",
            "description": (
                "Update a person's details: birthday, close_friend status, "
                "relationship, notes, last_contact."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {
                        "type": "string",
                        "description": "The person_id to update",
                    },
                    "display_name": {"type": "string"},
                    "relationship": {"type": "string"},
                    "birthday": {
                        "type": "string",
                        "description": "Birthday in YYYY-MM-DD format",
                    },
                    "close_friend": {"type": "boolean"},
                    "last_contact": {
                        "type": "string",
                        "description": "Last contact date in YYYY-MM-DD format",
                    },
                    "notes": {"type": "string"},
                },
                "required": ["person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_attachment",
            "description": (
                "Analyze an attached file. For images, returns a visual description. "
                "For documents (text, JSON, CSV), returns the file contents. "
                "Use the file_path from the [Attachments] info in the user's message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Local file path from the attachment info",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
]
