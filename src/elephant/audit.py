"""Consistency audit: detect duplicates, contradictions, stale threads, orphans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from elephant.data.store import DataStore


@dataclass
class AuditIssue:
    """A single audit finding."""

    category: str  # duplicate_memory, stale_thread, unknown_relationship, orphan_person, malformed
    severity: str  # warning, error
    message: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass
class AuditReport:
    """Full audit report."""

    issues: list[AuditIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


STALE_THREAD_DAYS = 60


def run_audit(store: DataStore) -> AuditReport:
    """Run all consistency checks and return a report."""
    report = AuditReport()
    _check_duplicate_memories(store, report)
    _check_stale_threads(store, report)
    _check_unknown_relationships(store, report)
    _check_orphan_people(store, report)
    _check_malformed_memories(store, report)
    return report


def _check_duplicate_memories(store: DataStore, report: AuditReport) -> None:
    """Find memories with same date + similar title."""
    memories = store.list_memories(limit=None)
    seen: dict[str, list[str]] = {}  # "date|title_lower" -> [memory_ids]
    for m in memories:
        key = f"{m.date}|{m.title.lower().strip()}"
        seen.setdefault(key, []).append(m.id)
    for key, ids in seen.items():
        if len(ids) > 1:
            report.issues.append(AuditIssue(
                category="duplicate_memory",
                severity="warning",
                message=f"Possible duplicate memories: {', '.join(ids)}",
                details={"memory_ids": ", ".join(ids), "key": key},
            ))


def _check_stale_threads(store: DataStore, report: AuditReport) -> None:
    """Find current_threads with last_mentioned_date > 60 days ago."""
    today = date.today()
    cutoff = today - timedelta(days=STALE_THREAD_DAYS)
    people = store.read_all_people()
    for person in people:
        for thread in person.current_threads:
            if thread.last_mentioned_date < cutoff:
                report.issues.append(AuditIssue(
                    category="stale_thread",
                    severity="warning",
                    message=(
                        f"{person.display_name}: thread '{thread.topic}' "
                        f"last mentioned {thread.last_mentioned_date} (>{STALE_THREAD_DAYS}d ago)"
                    ),
                    details={
                        "person_id": person.person_id,
                        "topic": thread.topic,
                        "last_mentioned": str(thread.last_mentioned_date),
                    },
                ))


def _check_unknown_relationships(store: DataStore, report: AuditReport) -> None:
    """Find people with relationship == 'unknown'."""
    people = store.read_all_people()
    for person in people:
        if person.relationship == "unknown":
            report.issues.append(AuditIssue(
                category="unknown_relationship",
                severity="warning",
                message=f"{person.display_name} has relationship='unknown'",
                details={"person_id": person.person_id},
            ))


def _check_orphan_people(store: DataStore, report: AuditReport) -> None:
    """Find names in memories that have no matching Person file."""
    memories = store.list_memories(limit=None)
    people = store.read_all_people()
    known_names: set[str] = {p.display_name.lower() for p in people}
    orphan_names: set[str] = set()
    for m in memories:
        for name in m.people:
            if name.lower() not in known_names:
                orphan_names.add(name)
    for name in sorted(orphan_names):
        report.issues.append(AuditIssue(
            category="orphan_person",
            severity="warning",
            message=f"'{name}' appears in memories but has no Person file",
            details={"name": name},
        ))


def _check_malformed_memories(store: DataStore, report: AuditReport) -> None:
    """Find memories with empty title or description."""
    memories = store.list_memories(limit=None)
    for m in memories:
        issues: list[str] = []
        if not m.title.strip():
            issues.append("empty title")
        if not m.description.strip():
            issues.append("empty description")
        if issues:
            report.issues.append(AuditIssue(
                category="malformed",
                severity="error",
                message=f"Memory {m.id}: {', '.join(issues)}",
                details={"memory_id": m.id, "problems": ", ".join(issues)},
            ))
