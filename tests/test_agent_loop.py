"""Tests for run_request's tool-use loop itself (step limit, cache_control
wiring) using a FAKE Anthropic client -- no network call, no API key, no
cost. The model's actual reasoning quality is validated separately by the
real (paid) run's saved transcripts in logs/ and logs_extended/; these
tests validate the LOOP's own control flow, which doesn't need a real
model to exercise.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import agent  # noqa: E402
from agent import MAX_STEPS, run_request  # noqa: E402
from cost_tracker import BudgetExceeded, CostTracker  # noqa: E402
import pytest  # noqa: E402


class _FakeUsage:
    def __init__(self):
        self.input_tokens = 10
        self.output_tokens = 5

    def model_dump(self):
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens}


class _FakeResponse:
    def __init__(self, content_blocks):
        self.content = content_blocks
        self.usage = _FakeUsage()


def _text_block(text):
    return types.SimpleNamespace(type="text", text=text)


def _tool_use_block(name, input_, id_):
    return types.SimpleNamespace(type="tool_use", name=name, input=input_, id=id_)


class _ScriptedClient:
    """Records every kwargs dict passed to messages.create and returns
    canned responses from a script, one per call, repeating the last one
    once the script is exhausted (so an infinite-step test doesn't crash)."""

    def __init__(self, script):
        self.script = script
        self.calls = []
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        idx = min(len(self.calls) - 1, len(self.script) - 1)
        return self.script[idx]


def test_tools_schema_is_clean_and_covers_every_dispatched_tool_name():
    """Guards against TOOL_INPUT_MODELS / TOOLS / _execute_tool's dispatch
    silently drifting apart -- the single-source-of-truth guarantee this
    whole validation layer depends on."""
    assert set(agent.TOOL_INPUT_MODELS) == set(agent.TOOL_DESCRIPTIONS)
    names_in_tools = {t["name"] for t in agent.TOOLS}
    assert names_in_tools == set(agent.TOOL_INPUT_MODELS)
    for tool in agent.TOOLS:
        schema = tool["input_schema"]
        assert "title" not in schema
        assert "$defs" not in schema
        for prop in schema.get("properties", {}).values():
            assert "title" not in prop


def test_cache_control_and_static_prompt_are_sent_on_every_call(portal, tmp_path):
    finish_response = _FakeResponse(
        [_tool_use_block("finish", {"status": "unresolved", "reason": "test"}, "t1")]
    )
    client = _ScriptedClient([finish_response])

    run_request(client, portal, {"request_id": "FAKE-1", "vendor_id": "V999"}, tmp_path)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["cache_control"] == agent.CACHE_CONTROL
    assert call["system"] == agent.SYSTEM_PROMPT
    assert call["tools"] == agent.TOOLS
    assert call["model"] == agent.MODEL


def test_step_limit_reached_without_finish_reports_failed_when_nothing_saved(portal, tmp_path):
    # Model only ever produces text, never calls a tool -> loop exhausts
    # MAX_STEPS via the "please proceed" nudge path every time.
    never_finishes = _FakeResponse([_text_block("thinking out loud forever")])
    client = _ScriptedClient([never_finishes])

    outcome = run_request(client, portal, {"request_id": "FAKE-2", "vendor_id": "V1"}, tmp_path)

    assert len(client.calls) == MAX_STEPS
    assert outcome.status == "failed"
    assert "Step limit" in outcome.reason
    assert outcome.new_drafts == 0


def test_step_limit_reached_after_a_real_save_reports_draft_not_failed(portal, tmp_path):
    # Step 1: the model successfully saves a draft via attempt_save.
    # Steps 2..N: the model just talks, never calls finish() -- this must
    # NOT be scored as "failed" once a draft genuinely exists.
    save_call = _FakeResponse(
        [
            _tool_use_block(
                "attempt_save",
                {
                    "request_id": "FAKE-3",
                    "vendor_id": "V1",
                    "line1": "a",
                    "city": "b",
                    "postal_code": "c",
                    "country": "d",
                },
                "t1",
            )
        ]
    )
    stalls_forever = _FakeResponse([_text_block("still thinking")])
    client = _ScriptedClient([save_call, stalls_forever])

    outcome = run_request(client, portal, {"request_id": "FAKE-3", "vendor_id": "V1"}, tmp_path)

    assert len(client.calls) == MAX_STEPS
    assert outcome.status == "draft"
    assert outcome.new_drafts == 1
    assert "Step limit" in outcome.reason
    assert portal.read_drafts()[0]["request_id"] == "FAKE-3"


def test_run_request_stops_before_call_when_cost_tracker_near_cap(portal, tmp_path):
    finish_response = _FakeResponse(
        [_tool_use_block("finish", {"status": "unresolved", "reason": "should never be reached"}, "t1")]
    )
    client = _ScriptedClient([finish_response])
    tracker = CostTracker(cap_usd=0.20)
    tracker.total_usd = 0.19  # within the safety margin of the cap

    with pytest.raises(BudgetExceeded):
        run_request(client, portal, {"request_id": "FAKE-4", "vendor_id": "V1"}, tmp_path, tracker)

    assert len(client.calls) == 0  # the API call itself must never happen


def test_run_request_adds_real_usage_to_shared_tracker(portal, tmp_path):
    finish_response = _FakeResponse(
        [_tool_use_block("finish", {"status": "unresolved", "reason": "test"}, "t1")]
    )
    client = _ScriptedClient([finish_response])
    tracker = CostTracker(cap_usd=0.20)

    run_request(client, portal, {"request_id": "FAKE-5", "vendor_id": "V1"}, tmp_path, tracker)

    assert tracker.calls == 1
    assert tracker.total_usd > 0
