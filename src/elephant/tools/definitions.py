"""OpenAI function-calling tool schemas for the conversational agent."""

from __future__ import annotations

from typing import Any

# Tools that mutate data — the LLM must call at least one of these
# or explicitly state "No update needed." in its response.
UPDATE_TOOLS: frozenset[str] = frozenset({
    "create_memory", "update_memory", "delete_memory",
    "update_person", "update_locations", "add_note",
})

QUERY_TOOLS: frozenset[str] = frozenset({
    "list_memories", "get_memory", "search_people",
    "get_person", "list_people", "describe_attachment",
})

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
                        "description": (
                            "Memory date (YYYY-MM-DD). Resolve relative "
                            "references ('two weeks ago', 'last month', "
                            "'yesterday') to an actual date using today's "
                            "date from the system context. Only default to "
                            "today if the event truly happened today."
                        ),
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
                    "attributes": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Flexible key-value metadata for the memory "
                            "(e.g. mood, weather, season, occasion, milestone_type). "
                            "Use snake_case keys with string values."
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
                    "attributes": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Flexible key-value metadata to merge into the memory. "
                            "New keys are added, existing keys are overwritten, "
                            "missing keys are preserved."
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
                "Update a person's details, or create a new person if they don't exist yet. "
                "Supports: birthday, other_names (nicknames), groups (list of group IDs), "
                "relationship (list of strings), notes, current_threads, "
                "interaction_frequency_target."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "person_id": {
                        "type": "string",
                        "description": "The person_id to update or create",
                    },
                    "create": {
                        "type": "boolean",
                        "description": (
                            "Set to true to create the person if they don't exist. "
                            "IMPORTANT: Before using create=true, you MUST first call "
                            "search_people to verify the person doesn't already exist, "
                            "and you MUST have their full name (first + family name). "
                            "Never create a person with only a first name. "
                            "Requires display_name and relationship."
                        ),
                    },
                    "display_name": {"type": "string"},
                    "other_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Nicknames, abbreviations, or alternative names "
                            "(e.g. 'Mike' for Michael, 'Beth' for "
                            "Elizabeth). Set when the user mentions "
                            "how someone is commonly called."
                        ),
                    },
                    "relationship": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Relationships to the user "
                            "(e.g. ['nephew', 'godson'])"
                        ),
                    },
                    "birthday": {
                        "type": "string",
                        "description": "Birthday in YYYY-MM-DD format",
                    },
                    "groups": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Group IDs this person belongs to "
                            "(e.g. ['close-friends', 'bjj', 'college'])"
                        ),
                    },
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
                    "attributes": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": (
                            "Flexible key-value metadata to merge into the person "
                            "(e.g. hobby, allergy, school). "
                            "New keys are added, existing keys are overwritten, "
                            "missing keys are preserved."
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
    {
        "type": "function",
        "function": {
            "name": "list_groups",
            "description": "List all people groups with their display names and colors.",
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
            "name": "update_group",
            "description": (
                "Create or update a people group. Groups are flat tags "
                "like 'bjj', 'college', 'close-friends'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "group_id": {
                        "type": "string",
                        "description": "Group identifier (e.g. 'bjj', 'close-friends')",
                    },
                    "display_name": {
                        "type": "string",
                        "description": "Human-readable group name",
                    },
                    "color": {
                        "type": "string",
                        "description": "Hex color for graph visualization (e.g. '#e91e8c')",
                    },
                },
                "required": ["group_id", "display_name"],
            },
        },
    },
]
