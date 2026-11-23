"""The model clients' translation of the conversation, without calling any model."""

import json

import httpx

from finance_agent.model import (
    ModelTurn,
    OpenAICompatibleClient,
    ScriptedClient,
    ToolCall,
    ToolTurn,
    UserTurn,
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


def test_openai_messages_carry_call_ids_and_json_arguments():
    messages = openai_messages(TRANSCRIPT)
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "tool", "assistant"]
    assert json.loads(messages[1]["tool_calls"][0]["function"]["arguments"]) == {"ticker": "AAPL"}
    assert messages[2]["tool_call_id"] == "a"


def test_openai_messages_leave_out_an_empty_reply():
    messages = openai_messages([UserTurn("hi"), ModelTurn(), UserTurn("again")])
    assert messages == [{"role": "user", "content": "hi"}, {"role": "user", "content": "again"}]


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
