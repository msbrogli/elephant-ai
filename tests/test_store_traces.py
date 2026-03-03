"""Tests for DataStore trace persistence methods."""

from elephant.data.store import DataStore
from elephant.tracing import IntentStep, LLMCallStep, Trace


class TestStoreTraces:
    def test_append_and_read_traces(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        t1 = Trace(
            database_name="family",
            message_id="msg-1",
            sender="alice",
            message_text="hello",
            intent="NEW_MEMORY",
            steps=[IntentStep(resolved_intent="NEW_MEMORY")],
        )
        t2 = Trace(
            database_name="family",
            message_id="msg-2",
            sender="bob",
            message_text="world",
            intent="DIGEST_FEEDBACK",
        )
        store.append_trace(t1)
        store.append_trace(t2)

        traces, total = store.read_traces()
        assert total == 2
        assert len(traces) == 2
        # Newest first
        assert traces[0].message_id == "msg-2"
        assert traces[1].message_id == "msg-1"

    def test_read_traces_empty(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        traces, total = store.read_traces()
        assert total == 0
        assert traces == []

    def test_read_traces_pagination(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        for i in range(10):
            store.append_trace(Trace(message_id=f"msg-{i}", message_text=f"text-{i}"))

        traces, total = store.read_traces(limit=3, offset=0)
        assert total == 10
        assert len(traces) == 3
        # Newest first
        assert traces[0].message_id == "msg-9"

        traces, total = store.read_traces(limit=3, offset=3)
        assert len(traces) == 3
        assert traces[0].message_id == "msg-6"

    def test_read_trace_by_id(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()

        trace = Trace(
            message_id="msg-1",
            message_text="test",
            steps=[LLMCallStep(method="chat", model="test")],
        )
        store.append_trace(trace)

        found = store.read_trace_by_id(trace.trace_id)
        assert found is not None
        assert found.trace_id == trace.trace_id
        assert len(found.steps) == 1

    def test_read_trace_by_id_not_found(self, data_dir):
        store = DataStore(data_dir)
        store.initialize()
        assert store.read_trace_by_id("nonexistent") is None

    def test_trace_steps_discriminated(self, data_dir):
        """Verify step types are correctly deserialized."""
        store = DataStore(data_dir)
        store.initialize()

        trace = Trace(
            message_id="msg-1",
            steps=[
                IntentStep(resolved_intent="NEW_MEMORY"),
                LLMCallStep(method="chat_with_tools", model="gpt-4"),
            ],
        )
        store.append_trace(trace)

        found = store.read_trace_by_id(trace.trace_id)
        assert found is not None
        assert found.steps[0].step_type == "intent"
        assert found.steps[1].step_type == "llm_call"
