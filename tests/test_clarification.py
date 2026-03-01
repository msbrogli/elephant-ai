"""Tests for brain clarification: question gen, answer processing, rate limiting."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

from elephant.brain.clarification import (
    MAX_PENDING_QUESTIONS,
    generate_question_for_memory,
    is_thin_memory,
    process_answer,
)
from elephant.data.models import (
    Memory,
    PendingQuestion,
    PendingQuestionsFile,
    Person,
    PreferencesFile,
)
from elephant.data.store import DataStore
from elephant.llm.client import LLMResponse


def _make_memory(**kwargs):
    defaults = {
        "id": "20260224_test",
        "date": date(2026, 2, 24),
        "title": "Test",
        "type": "daily",
        "description": "Short",
        "people": [],
        "source": "WhatsApp",
    }
    defaults.update(kwargs)
    return Memory(**defaults)


class TestIsThinMemory:
    def test_thin_memory(self):
        memory = _make_memory(description="Went to park")
        assert is_thin_memory(memory) is True

    def test_detailed_memory_not_thin(self):
        memory = _make_memory(
            description="We went to the park and had a wonderful time playing on the swings",
            people=["Lily", "Dad"],
            location="Central Park",
        )
        assert is_thin_memory(memory) is False

    def test_short_but_many_people_and_location(self):
        # Short description but has both people and location
        memory = _make_memory(
            description="Had fun",
            people=["Lily", "Dad"],
            location="Home",
        )
        # short_desc=True, few_people=False, no_location=False
        # is_thin = short_desc and (few_people or no_location) = True and (False or False) = False
        assert is_thin_memory(memory) is False


class TestGenerateQuestionForMemory:
    async def test_generates_question(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(content="Who was with you?", model="m", usage={})
        )

        memory = _make_memory(description="Went to park")
        people: list[Person] = []
        prefs = PreferencesFile()
        question = await generate_question_for_memory(memory, llm, "m", people, prefs, store)

        assert question is not None
        assert question.type == "memory_enrichment"
        assert question.question == "Who was with you?"
        assert question.status == "pending"

    async def test_rate_limited(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Add max pending questions
        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id=f"q_{i}",
                    type="memory_enrichment",
                    subject="test",
                    status="pending",
                    created_at=datetime.now(UTC),
                )
                for i in range(MAX_PENDING_QUESTIONS)
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        memory = _make_memory()
        people: list[Person] = []
        prefs = PreferencesFile()
        question = await generate_question_for_memory(memory, llm, "m", people, prefs, store)
        assert question is None


class TestProcessAnswer:
    async def test_answers_question(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        # Create a memory
        memory = _make_memory(
            id="20260224_park_day",
            description="Went to park",
        )
        store.write_memory(memory)

        # Create a pending question
        pq = PendingQuestionsFile(
            questions=[
                PendingQuestion(
                    id="q_001",
                    type="memory_enrichment",
                    subject="20260224_park_day",
                    question="Who was with you?",
                    status="asked",
                    created_at=datetime.now(UTC),
                )
            ]
        )
        store.write_pending_questions(pq)

        llm = AsyncMock()
        llm.chat = AsyncMock(
            return_value=LLMResponse(
                content="Went to the park with Lily and Dad. They played on the swings together.",
                model="m",
                usage={},
            )
        )

        success = await process_answer("q_001", "Lily and Dad came with me", llm, "m", store)
        assert success is True

        # Verify question was marked answered
        updated_pq = store.read_pending_questions()
        assert updated_pq.questions[0].status == "answered"
        assert updated_pq.questions[0].answer == "Lily and Dad came with me"

    async def test_nonexistent_question(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        llm = AsyncMock()
        success = await process_answer("q_nonexistent", "test", llm, "m", store)
        assert success is False
