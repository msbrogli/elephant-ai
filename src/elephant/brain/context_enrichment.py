"""Parse user answers to update context.yaml and people.yaml."""

import logging
from datetime import UTC, datetime
from typing import Any

import yaml

from elephant.data.store import DataStore
from elephant.git_ops import GitRepo
from elephant.llm.client import LLMClient
from elephant.llm.prompts import enrich_context

logger = logging.getLogger(__name__)

# Accept both singular and plural key variants from LLM responses.
_FAMILY_KEYS = {"family_member", "family_members"}
_FRIEND_KEYS = {"friend", "friends"}
_LOCATION_KEYS = {"location", "locations"}
_NOTE_KEYS = {"note", "notes"}
_PERSON_UPDATE_KEYS = {"person_update", "person_updates"}


def _as_list(value: Any) -> list[Any]:
    """Normalise a value that may be a single item or a list into a list."""
    if isinstance(value, list):
        return value
    return [value]


def _get_values(updates: dict[str, Any], keys: set[str]) -> list[Any]:
    """Collect values from *updates* for any matching key, returned as a flat list."""
    items: list[Any] = []
    for key in keys:
        if key in updates:
            items.extend(_as_list(updates[key]))
    return items


async def process_context_update(
    text: str,
    llm: LLMClient,
    model: str,
    store: DataStore,
    git: GitRepo,
) -> bool:
    """Process a context update message from the user."""
    now = datetime.now(UTC)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")
    current_context = store.read_context()
    messages = enrich_context(text, current_context, now=now_str)
    response = await llm.chat(messages, model=model, temperature=0.3)

    try:
        updates = yaml.safe_load(response.content or "")
    except yaml.YAMLError:
        logger.warning("Failed to parse context update YAML from LLM")
        return False

    if not isinstance(updates, dict):
        logger.warning("LLM returned non-dict context update: %s", type(updates).__name__)
        return False

    changed = False

    # Handle family member updates
    for member in _get_values(updates, _FAMILY_KEYS):
        if isinstance(member, dict) and "name" in member:
            changed |= _add_family_member(current_context, member)

    # Handle friend updates
    for friend in _get_values(updates, _FRIEND_KEYS):
        if isinstance(friend, dict) and "name" in friend:
            changed |= _add_friend(current_context, friend)

    # Handle location updates
    for loc in _get_values(updates, _LOCATION_KEYS):
        if isinstance(loc, dict) and "name" in loc:
            locations = current_context.setdefault("locations", {})
            locations[loc["name"]] = loc.get("description", "")
            changed = True

    # Handle note updates
    today = now.strftime("%Y-%m-%d")
    for note in _get_values(updates, _NOTE_KEYS):
        if note:
            notes = current_context.setdefault("notes", [])
            notes.append({"text": str(note), "date": today})
            changed = True

    # Handle person updates (update existing person info)
    for pu in _get_values(updates, _PERSON_UPDATE_KEYS):
        if isinstance(pu, dict) and "name" in pu:
            changed |= _update_person(store, pu)

    if changed:
        store.write_context(current_context)
        git.auto_commit("context", "Context update from user")
        logger.info("Context updated from user message")
    else:
        logger.warning("No recognised updates in LLM response: %s", list(updates.keys()))

    return changed


def _add_family_member(context: dict[str, Any], member: dict[str, Any]) -> bool:
    """Add a family member to context."""
    family = context.setdefault("family", {})
    members = family.setdefault("members", [])
    # Check if already exists
    for existing in members:
        if existing.get("name") == member["name"]:
            existing.update(member)
            return True
    members.append(member)
    return True


def _add_friend(context: dict[str, Any], friend: dict[str, Any]) -> bool:
    """Add a friend to context."""
    friends = context.setdefault("friends", [])
    for existing in friends:
        if existing.get("name") == friend["name"]:
            existing.update(friend)
            return True
    friends.append(friend)
    return True


def _update_person(store: DataStore, update: dict[str, Any]) -> bool:
    """Update a person in the people directory."""
    name = update["name"]
    field = update.get("field")
    value = update.get("value")
    if not field or value is None:
        return False

    for person in store.read_all_people():
        if person.display_name == name and hasattr(person, field):
            updated = person.model_copy(update={field: value})
            store.write_person(updated)
            return True
    return False
