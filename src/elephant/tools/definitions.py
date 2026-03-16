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

# Maximum allowed length for string-type arguments
MAX_STRING_ARG_LENGTH = 5000

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_memories",
            "description": (
                "Search and filter memories. Returns summaries (id, date, title, type, "
                "description, people, location) — not full details. Use when the user asks "
                "'what happened last week?', 'show me memories with Dad', or 'any trips in "
                "January?'. Supports filtering by date range, people, type, tags, and "
                "free-text substring search in title/description. Returns newest-first, "
                "default limit 20. For full details of a specific memory (tags, content, "
                "corrections, media), use get_memory instead."
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
                        "description": (
                            "Free-text substring search in title and description "
                            "(case-insensitive, exact substring — not fuzzy or semantic). "
                            "Use specific keywords."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": (
                            "Max results to return (default 20, newest first). "
                            "Set to a higher number or null for all results."
                        ),
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
            "description": (
                "Get the complete record of a single memory by its ID, including all "
                "fields: tags, content, corrections history, media, nostalgia_score, "
                "participants, and attributes. Use when you already have a memory_id "
                "(e.g. from list_memories results) and need full details. Do NOT use "
                "this to search — use list_memories to find memories first."
            ),
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
                "Create a new memory for a specific event or experience that happened on "
                "a particular date. Use when the user describes something that happened: "
                "'We went to the park yesterday', 'Mom's birthday was amazing'. Do NOT "
                "use for general facts, preferences, or ongoing state — use add_note for "
                "preferences and update_person for life updates (new job, new hobby). If "
                "confidence is below 0.6, returns a clarification request instead of "
                "saving. Unknown people trigger a warning unless auto_create_people=true."
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
                        "description": (
                            "0.5-2.0 importance weight. Use 0.5 for mundane daily events, "
                            "1.0 for normal outings/celebrations, 1.5 for significant "
                            "milestones, 2.0 for once-in-a-lifetime moments (birth, wedding)."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Relevant tags",
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Optional full narrative prose expanding on the description. "
                            "Use for rich, detailed memories where the user provided a "
                            "longer story."
                        ),
                    },
                    "participants": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "person_ids of people involved",
                    },
                    "confidence": {
                        "type": "number",
                        "description": (
                            "0.0-1.0. Set below 0.6 if key details are ambiguous or "
                            "missing — this triggers a clarification request instead of "
                            "saving. Default 1.0."
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
            "description": (
                "Update fields on an existing memory by its ID. Use when the user "
                "corrects or adds details to a previously saved memory: 'actually that "
                "was at the beach, not the park', 'add Grandma to yesterday's dinner'. "
                "For past memories (before today), changes are tracked as corrections "
                "preserving history. Updatable fields: title, description, people, "
                "location, tags, attributes. Requires a reason when updating past "
                "memories. Do NOT use to create new memories — use create_memory instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory ID to update",
                    },
                    "title": {
                        "type": "string",
                        "description": "New value to replace the existing one",
                    },
                    "description": {
                        "type": "string",
                        "description": "New value to replace the existing one",
                    },
                    "people": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New value to replace the existing one",
                    },
                    "location": {
                        "type": "string",
                        "description": "New value to replace the existing one",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New value to replace the existing one",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "Explanation of why this memory is being corrected "
                            "(required for past memories, as changes are tracked "
                            "in correction history)."
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
            "description": (
                "Delete a memory by ID. This is a two-step process: the first call "
                "(without confirm) returns a preview of what will be deleted; you must "
                "call again with confirm=true to actually delete. Always show the preview "
                "to the user and get confirmation before the second call."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "The memory ID to delete",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": (
                            "Set to true to confirm deletion. "
                            "First call without this to preview what will be deleted."
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
            "name": "search_people",
            "description": (
                "Find people by name using fuzzy matching. Returns matches with "
                "person_id, display_name, relationship, match_score, current_threads, "
                "and last_contact date. Use when the user mentions someone by first name "
                "and you need to find their person_id, or to verify if someone already "
                "exists before creating them. Handles partial names and nicknames. For a "
                "full profile with life events, archived threads, and preferences, use "
                "get_person with the person_id from these results. Do NOT use list_people "
                "for name lookups — it returns everyone without filtering."
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
                "Get the complete profile of a person by their person_id, including "
                "life_events, relationships, archived_threads, preferences, notes, and "
                "attributes. Use when you need full details about someone (e.g. to answer "
                "'tell me about John' or to check archived threads). Requires an exact "
                "person_id — use search_people first if you only have a name."
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
            "description": (
                "List ALL known people with summary info: person_id, display_name, "
                "relationship, birthday, groups, current_threads, and last_contact. "
                "Use when the user asks 'who do I know?', 'show me everyone', or "
                "'who haven't I talked to recently?'. Returns the entire roster — "
                "do NOT use for finding a specific person by name (use search_people "
                "instead)."
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
            "name": "update_person",
            "description": (
                "Update a person's profile, or create a new person if they don't exist. "
                "Use for ongoing life state changes: 'John got a new job', 'Sarah is "
                "moving to Boston', 'add Mike's birthday'. Supports: display_name, "
                "relationship, birthday, other_names (nicknames), groups, notes, "
                "current_threads (replaces list), archive_threads (moves topics to "
                "archive), interaction_frequency_target, and attributes (merged key-value "
                "metadata like hobby, allergy, school). When creating (create=true): you "
                "MUST first call search_people to verify the person doesn't exist, and you "
                "MUST have their full name (first + family). Canonical field changes "
                "(birthday, relationship, display_name) require force=true if they conflict "
                "with existing values. Do NOT use for specific dated events — use "
                "create_memory instead."
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
            "description": (
                "Add or update named locations in the family's preferences. Use when the "
                "user mentions a new recurring place: 'we call Grandma's house The Ranch', "
                "'our usual park is Riverside Park on 5th Ave'. Locations is a "
                "name-to-description mapping (e.g. {\"The Ranch\": \"Grandma's house in "
                "Montana\"}). Existing locations are preserved; only provided keys are "
                "added or overwritten."
            ),
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
            "description": (
                "Add a freeform note to the family's preferences. Use for general context, "
                "preferences, or reminders that aren't tied to a specific date or person: "
                "'we're vegetarian', 'prefer heartfelt tone in digests', 'anniversary is "
                "always celebrated at The Ranch'. Do NOT use for dated events (use "
                "create_memory) or person-specific facts (use update_person with attributes "
                "or notes)."
            ),
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
                "Analyze an attached file. For images (jpg, png, gif, webp): sends to "
                "vision model and returns a narrative description of what's visible. For "
                "documents (text, JSON, CSV): returns the raw file contents (truncated to "
                "100KB). Use the file_path from the [Attachments] section in the user's "
                "message. Always call this BEFORE creating a memory from an attachment — "
                "describe first, then create_memory with the description."
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
            "description": (
                "List all people groups with their group_id, display_name, and color. "
                "Groups are flat tags (e.g. 'bjj', 'college', 'close-friends') used to "
                "organize people."
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
            "name": "update_group",
            "description": (
                "Create or update a people group. Groups are flat tags like 'bjj', "
                "'college', 'close-friends' with a display name and optional hex color "
                "for visualization. Use when the user defines a new group or wants to "
                "rename/recolor an existing one."
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

# Derived allowlist — only these tool names are valid for dispatch
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    d["function"]["name"] for d in TOOL_DEFINITIONS
)

# Lookup: tool_name → parameter schema
_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    d["function"]["name"]: d["function"]["parameters"]
    for d in TOOL_DEFINITIONS
}


def validate_tool_args(tool_name: str, args: dict[str, Any]) -> list[str]:
    """Validate tool arguments against the schema. Returns a list of error messages."""
    schema = _TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return [f"Unknown tool: {tool_name}"]

    errors: list[str] = []
    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required fields
    for field in required:
        if field not in args:
            errors.append(f"Missing required field: {field}")

    # Check types and enforce string size limits
    for key, value in args.items():
        if key not in properties:
            continue  # Extra fields are tolerated (LLMs may hallucinate)
        prop_schema = properties[key]
        expected_type = prop_schema.get("type")

        if expected_type == "string" and isinstance(value, str):
            if len(value) > MAX_STRING_ARG_LENGTH:
                errors.append(
                    f"Field '{key}' exceeds max length "
                    f"({len(value)} > {MAX_STRING_ARG_LENGTH})"
                )
        elif expected_type == "integer" and not isinstance(value, int):
            errors.append(f"Field '{key}' must be an integer, got {type(value).__name__}")
        elif expected_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{key}' must be a number, got {type(value).__name__}")
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append(f"Field '{key}' must be a boolean, got {type(value).__name__}")
        elif expected_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{key}' must be an array, got {type(value).__name__}")
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{key}' must be an object, got {type(value).__name__}")

    return errors
