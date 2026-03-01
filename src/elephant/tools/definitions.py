"""OpenAI function-calling tool schemas for the conversational agent."""

from __future__ import annotations

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": (
                "Search and list memories. Use to answer questions about what happened, "
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
                    "memory_type": {
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
            "name": "get_memory",
            "description": "Get full details of a specific memory by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory ID (e.g. 20260224_park_day)",
                    },
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_memory",
            "description": (
                "Create a new memory. Use when the user describes something that happened."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the memory",
                    },
                    "date": {
                        "type": "string",
                        "description": "Memory date (YYYY-MM-DD). Use today if not specified.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Memory time (HH:MM) or null",
                    },
                    "type": {
                        "type": "string",
                        "enum": [
                            "milestone", "daily", "outing", "celebration",
                            "health", "travel", "mundane", "other",
                        ],
                        "description": "Memory type",
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
                    "content": {
                        "type": "string",
                        "description": "Full narrative prose of the memory",
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "person_ids of people involved",
                    },
                    "confidence": {
                        "type": "number",
                        "description": (
                            "Confidence score 0.0-1.0 for how sure you are about this memory. "
                            "Low-confidence memories trigger clarification."
                        ),
                    },
                    "auto_create_people": {
                        "type": "boolean",
                        "description": (
                            "Set to true to auto-create Person files for unknown people. "
                            "Only use after confirming with the user."
                        ),
                    },
                },
                "required": ["title", "date", "type", "description", "people"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_memory",
            "description": "Update fields on an existing memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory ID to update",
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
                    "reason": {
                        "type": "string",
                        "description": (
                            "Reason for the update (required when updating past memories)"
                        ),
                    },
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_memory",
            "description": "Delete a memory by ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory ID to delete",
                    },
                },
                "required": ["memory_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_people",
            "description": (
                "Search for people by name (partial match). Returns matches with "
                "relationship, current threads, and last contact. Use to disambiguate "
                "when the user mentions a person by first name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to search for (case-insensitive partial match)",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_person",
            "description": (
                "Get full person profile by person_id including threads, "
                "connections, life events."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {
                        "type": "string",
                        "description": "The person_id to look up",
                    },
                },
                "required": ["person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_people",
            "description": "List all known people with summary info including current threads.",
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
                "relationship, notes, last_contact, current_threads, "
                "interaction_frequency_target."
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
                    "notes": {"type": "string"},
                    "current_threads": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "topic": {"type": "string"},
                                "latest_update": {"type": "string"},
                                "last_mentioned_date": {
                                    "type": "string",
                                    "description": "YYYY-MM-DD",
                                },
                            },
                            "required": ["topic", "latest_update", "last_mentioned_date"],
                        },
                        "description": "Replace current threads with this list",
                    },
                    "interaction_frequency_target": {
                        "type": "integer",
                        "description": "Target days between contacts",
                    },
                    "archive_threads": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Topic names to move from current_threads to archived_threads."
                        ),
                    },
                    "force": {
                        "type": "boolean",
                        "description": (
                            "Set to true to force-update canonical fields "
                            "(birthday, relationship, display_name) even if they differ."
                        ),
                    },
                },
                "required": ["person_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_locations",
            "description": "Update known locations in preferences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "locations": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "Location name -> description mapping to add/update",
                    },
                },
                "required": ["locations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note",
            "description": "Add a freeform note to preferences.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "The note to add",
                    },
                },
                "required": ["note"],
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
