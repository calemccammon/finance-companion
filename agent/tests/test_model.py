"""The model clients' translation of the conversation, without calling any model."""

import json
from collections import Counter

import httpx
import httpx2
from anthropic import Anthropic, DefaultHttpxClient
from anthropic.types import Message

from finance_agent.model import (
    ClaudeClient,
    ModelTurn,
    OpenAICompatibleClient,
    ScriptedClient,
    ToolCall,
    ToolTurn,
    UserTurn,
    claude_messages,
    claude_turn,
    openai_messages,
)

CALL_A = ToolCall(name="price_history", arguments={"ticker": "AAPL"}, id="a")
CALL_B = ToolCall(name="macro_snapshot", arguments={}, id="b")
TRANSCRIPT = [
    UserTurn("How is Apple doing?"),
    ModelTurn(tool_calls=(CALL_A, CALL_B)),
    ToolTurn(CALL_A, {"storedAt": "/r1"}),
    ToolTurn(CALL_B, {"storedAt": "/r2"}),
    ModelTurn(text="<a2ui-json>[]</a2ui-json>"),
]


def test_claude_messages_put_one_turns_results_and_what_follows_in_one_user_message():
    correction = UserTurn("That layout was rejected.")
    messages = claude_messages([*TRANSCRIPT[:4], correction])

    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert [b["type"] for b in messages[1]["content"]] == ["tool_use", "tool_use"]
    results = messages[2]["content"]
    assert [b.get("tool_use_id") for b in results] == ["a", "b", None]
    assert json.loads(results[0]["content"]) == {"storedAt": "/r1"}
    assert results[2] == {"type": "text", "text": "That layout was rejected."}


def test_a_failed_tool_is_marked_as_an_error_for_claude():
    failed = ToolTurn(CALL_A, {"error": "Unknown ticker"})
    assert claude_messages([TRANSCRIPT[0], TRANSCRIPT[1], failed])[2]["content"][0]["is_error"] is True


def test_an_empty_reply_is_left_out_rather_than_sent_empty():
    messages = claude_messages([UserTurn("hi"), ModelTurn(), UserTurn("again")])
    assert messages == [
        {"role": "user", "content": [{"type": "text", "text": "hi"}, {"type": "text", "text": "again"}]}
    ]


def message(*content, stop_reason="tool_use"):
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 900, "output_tokens": 40, "cache_read_input_tokens": 7000},
        "content": list(content),
    }


THINKING = {"type": "thinking", "thinking": "", "signature": "sig-1"}
CALL = {"type": "tool_use", "id": "toolu_1", "name": "price_history", "input": {"ticker": "AAPL"}}


def test_claude_turn_reads_calls_and_text_and_keeps_every_block():
    turn = claude_turn(Message.model_validate(message(THINKING, {"type": "text", "text": "Fetching."}, CALL)))

    assert turn.text == "Fetching."
    assert turn.tool_calls == (ToolCall(name="price_history", arguments={"ticker": "AAPL"}, id="toolu_1"),)
    assert [b.type for b in turn.raw] == ["thinking", "text", "tool_use"]


def test_the_claude_client_sends_its_thinking_back_unchanged_and_counts_tokens():
    sent = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        sent.append(json.loads(request.content))
        return httpx2.Response(200, json=message(THINKING, CALL))

    http = DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    client = ClaudeClient(client=Anthropic(api_key="test", http_client=http, max_retries=0))
    tools = [
        {"name": "price_history", "description": "d", "parameters": {"type": "object", "additionalProperties": False}}
    ]

    first = client.reply("rules", [UserTurn("How is Apple doing?")], tools)
    client.reply(
        "rules", [UserTurn("How is Apple doing?"), first, ToolTurn(first.tool_calls[0], {"storedAt": "/r1"})], tools
    )

    body = sent[1]
    assert body["model"] == "claude-haiku-5-5" and body["system"] == "rules"
    assert body["tools"] == [{"name": "price_history", "description": "d", "input_schema": tools[0]["parameters"]}]
    assert body["cache_control"] == {"type": "ephemeral"}
    assert "temperature" not in body
    # The thinking block and its signature go back exactly as they came.
    assert body["messages"][1] == {"role": "assistant", "content": [THINKING, CALL]}
    assert body["messages"][2]["content"][0]["tool_use_id"] == "toolu_1"
    assert client.usage == Counter(input_tokens=1800, output_tokens=80, cache_read_input_tokens=14000)


def test_openai_messages_carry_call_ids_and_json_arguments():
    messages = openai_messages(TRANSCRIPT)
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "tool", "assistant"]
    assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == {"ticker": "AAPL"}
    assert messages[2]["tool_call_id"] == "a"


def test_the_openai_compatible_client_reads_tool_calls_and_text():
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "x1", "type": "function", "function": {"name": "macro_snapshot", "arguments": "{}"}}],
        }
        return httpx.Response(200, json={"choices": [{"message": message}]})

    client = OpenAICompatibleClient(
        "http://model/v1", "local", http=httpx.Client(transport=httpx.MockTransport(handler))
    )
    turn = client.reply("system", [UserTurn("hi")], [{"name": "macro_snapshot", "description": "d", "parameters": {}}])

    assert turn.tool_calls[0].name == "macro_snapshot" and turn.tool_calls[0].id == "x1"
    assert sent[0]["messages"][0] == {"role": "system", "content": "system"}
    assert sent[0]["tools"][0]["type"] == "function"


def test_a_script_can_be_read_from_a_file(tmp_path):
    script = tmp_path / "script.json"
    script.write_text(json.dumps([{"tool_calls": [{"name": "macro_snapshot", "arguments": {}}]}, {"text": "done"}]))
    client = ScriptedClient.from_file(script)

    assert client.reply("", [], []).tool_calls[0].name == "macro_snapshot"
    assert client.reply("", [], []).text == "done"
