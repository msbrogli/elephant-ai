"""Tests for tracing module."""

from elephant.tracing import (
    GitCommitStep,
    IntentStep,
    LLMCallStep,
    ToolExecStep,
    Trace,
    finish_trace,
    get_current_trace,
    record_step,
    start_trace,
)


class TestTraceLifecycle:
    def test_start_sets_contextvar(self):
        trace = start_trace("db1", "msg-1", "alice", "hello")
        assert get_current_trace() is trace
        assert trace.database_name == "db1"
        assert trace.message_id == "msg-1"
        assert trace.sender == "alice"
        assert trace.message_text == "hello"
        assert trace.started_at is not None
        assert trace.finished_at is None
        # Cleanup
        finish_trace()

    def test_record_step_appends(self):
        start_trace("db1", "msg-2", "bob", "hi")
        step = IntentStep(resolved_intent="NEW_MEMORY", message_text="hi", sender="bob")
        record_step(step)
        trace = get_current_trace()
        assert trace is not None
        assert len(trace.steps) == 1
        assert trace.steps[0].step_type == "intent"
        finish_trace()

    def test_record_step_noop_without_trace(self):
        """record_step should silently do nothing if no trace is active."""
        assert get_current_trace() is None
        record_step(IntentStep())  # Should not raise

    def test_finish_returns_trace_and_clears(self):
        start_trace("db1", "msg-3", "carol", "test")
        record_step(IntentStep(resolved_intent="NEW_MEMORY"))
        finished = finish_trace(intent="NEW_MEMORY", final_response="Done!", error=None)
        assert finished is not None
        assert finished.intent == "NEW_MEMORY"
        assert finished.final_response == "Done!"
        assert finished.finished_at is not None
        assert finished.error is None
        assert get_current_trace() is None

    def test_finish_with_error(self):
        start_trace("db1", "msg-4", "dave", "broken")
        finished = finish_trace(error="ValueError: bad input")
        assert finished is not None
        assert finished.error == "ValueError: bad input"

    def test_finish_noop_without_trace(self):
        assert finish_trace() is None


class TestStepModels:
    def test_llm_call_step(self):
        step = LLMCallStep(
            method="chat_with_tools",
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=1024,
            messages=[{"role": "user", "content": "hi"}],
            response_content="Hello!",
            response_tool_calls=[],
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )
        assert step.step_type == "llm_call"
        data = step.model_dump(mode="json")
        assert data["method"] == "chat_with_tools"
        assert data["model"] == "gpt-4o-mini"

    def test_tool_exec_step(self):
        step = ToolExecStep(
            tool_call_id="tc-1",
            function_name="create_memory",
            arguments='{"title": "Test"}',
            result='{"status": "ok"}',
        )
        assert step.step_type == "tool_exec"
        data = step.model_dump(mode="json")
        assert data["function_name"] == "create_memory"

    def test_git_commit_step(self):
        step = GitCommitStep(sha="abc123", message="[memory] Test")
        assert step.step_type == "git_commit"

    def test_intent_step(self):
        step = IntentStep(resolved_intent="NEW_MEMORY", message_text="hi", sender="alice")
        assert step.step_type == "intent"


class TestTraceModel:
    def test_trace_serialization_roundtrip(self):
        trace = Trace(
            database_name="family",
            message_id="msg-1",
            sender="alice",
            message_text="We went to the park",
            intent="NEW_MEMORY",
            final_response="Got it!",
            steps=[
                IntentStep(resolved_intent="NEW_MEMORY"),
                LLMCallStep(method="chat", model="test"),
                ToolExecStep(function_name="create_memory"),
                GitCommitStep(sha="abc123"),
            ],
        )
        json_str = trace.model_dump_json()
        restored = Trace.model_validate_json(json_str)
        assert restored.trace_id == trace.trace_id
        assert restored.database_name == "family"
        assert len(restored.steps) == 4

    def test_trace_auto_generates_id(self):
        t1 = Trace()
        t2 = Trace()
        assert t1.trace_id != t2.trace_id
        assert len(t1.trace_id) == 16
