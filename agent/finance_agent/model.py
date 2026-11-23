"""The language model, behind one small interface.

The agent keeps the conversation in its own neutral shape and each client
translates it for one API: Claude, any OpenAI-compatible endpoint (a local
Ollama, for one), or a script of replies for tests.
"""

import json
import logging
import os
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass(frozen=True)
class UserTurn:
    text: str


@dataclass(frozen=True)
class ModelTurn:
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    # The provider's own record of the turn, opaque to the agent, which the client that
    # made it sends back unchanged: Claude's thinking blocks must return exactly as they came.
    raw: tuple = field(default=(), compare=False)


@dataclass(frozen=True)
class ToolTurn:
    call: ToolCall
    result: dict


Turn = UserTurn | ModelTurn | ToolTurn


class ModelClient(Protocol):
    name: str

    def reply(self, system: str, transcript: Sequence[Turn], tools: list[dict]) -> ModelTurn:
        """The model's next turn: text, tool calls, or both."""
        ...


# --- Claude -----------------------------------------------------------------

log = logging.getLogger(__name__)

DEFAULT_CLAUDE = "claude-haiku-5-5"


class ClaudeClient:
    """Claude through Anthropic's SDK. Reads ANTHROPIC_API_KEY."""

    def __init__(self, model: str = DEFAULT_CLAUDE, client=None):
        import anthropic

        self.name = f"anthropic:{model}"
        self._model = model
        # The SDK waits out rate limits and brief outages (429, 5xx); a new key's limits are low.
        self._client = client or anthropic.Anthropic(max_retries=6)
        # Tokens used so far, by kind, so a run can say what it cost.
        self.usage: Counter = Counter()

    def reply(self, system: str, transcript: Sequence[Turn], tools: list[dict]) -> ModelTurn:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=16000,
            system=system,
            tools=claude_tools(tools),
            messages=claude_messages(transcript),
            # The rules, catalog and tools are the same on every request: cached, they cost a tenth.
            cache_control={"type": "ephemeral"},
            # Haiku's own default, set here so it does not move under us.
            output_config={"effort": "medium"},
        )
        for kind in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            self.usage[kind] += getattr(response.usage, kind, 0) or 0
        if response.stop_reason in ("refusal", "max_tokens"):
            log.warning("Claude stopped with %s", response.stop_reason)
        return claude_turn(response)


def claude_turn(response) -> ModelTurn:
    """Claude's reply as a turn: its tool calls and its text, with every block kept to send back."""
    blocks = tuple(response.content or ())
    calls = tuple(ToolCall(name=b.name, arguments=dict(b.input or {}), id=b.id) for b in blocks if b.type == "tool_use")
    text = "".join(b.text for b in blocks if b.type == "text")
    return ModelTurn(text=text, tool_calls=calls, raw=blocks)


def claude_tools(tools: list[dict]) -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]


def claude_messages(transcript: Sequence[Turn]) -> list[dict]:
    """The transcript as Claude `messages`. A model turn goes back as it came; the results of
    one turn's calls, and any text after them, go together in the next user message."""
    messages: list[dict] = []

    def user(block: dict) -> None:
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"].append(block)
        else:
            messages.append({"role": "user", "content": [block]})

    for turn in transcript:
        match turn:
            case UserTurn(text=text):
                user({"type": "text", "text": text})
            case ModelTurn(text=text, tool_calls=calls, raw=raw):
                if raw:
                    content = list(raw)
                else:
                    content = [{"type": "text", "text": text}] if text else []
                    content += [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments} for c in calls]
                # A turn with nothing in it (a refusal) cannot be sent; the user message after it carries on.
                if content:
                    messages.append({"role": "assistant", "content": content})
            case ToolTurn(call=call, result=result):
                block = {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(result)}
                if "error" in result:
                    block["is_error"] = True
                user(block)
    return messages


# --- OpenAI-compatible ------------------------------------------------------


class OpenAICompatibleClient:
    """Any chat-completions endpoint with tool calling, such as Ollama's `/v1`."""

    def __init__(self, base_url: str, model: str, api_key: str | None = None, http: httpx.Client | None = None):
        self.name = f"openai:{model}"
        self._model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = http or httpx.Client(timeout=300)

    def reply(self, system: str, transcript: Sequence[Turn], tools: list[dict]) -> ModelTurn:
        body = {
            "model": self._model,
            "temperature": 0.2,
            "messages": [{"role": "system", "content": system}, *openai_messages(transcript)],
            "tools": [{"type": "function", "function": t} for t in tools],
        }
        response = self._http.post(self._url, json=body, headers=self._headers)
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        calls = tuple(
            ToolCall(
                name=c["function"]["name"],
                arguments=_arguments(c["function"].get("arguments")),
                id=c.get("id") or uuid.uuid4().hex[:12],
            )
            for c in message.get("tool_calls") or []
        )
        return ModelTurn(text=message.get("content") or "", tool_calls=calls)


def _arguments(raw: str | dict | None) -> dict:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def openai_messages(transcript: Sequence[Turn]) -> list[dict]:
    messages: list[dict] = []
    for turn in transcript:
        match turn:
            case UserTurn(text=text):
                messages.append({"role": "user", "content": text})
            case ModelTurn(text=text, tool_calls=calls):
                message: dict = {"role": "assistant", "content": text or None}
                if calls:
                    message["tool_calls"] = [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                        }
                        for c in calls
                    ]
                messages.append(message)
            case ToolTurn(call=call, result=result):
                messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})
    return messages


# --- scripted ----------------------------------------------------------------


class ScriptedClient:
    """Replies from a script, in order: for tests, and for running the app without a model."""

    def __init__(self, replies: Sequence[ModelTurn], name: str = "scripted"):
        self.name = name
        self._replies = list(replies)
        self.seen: list[tuple[str, list[Turn]]] = []

    def reply(self, system: str, transcript: Sequence[Turn], tools: list[dict]) -> ModelTurn:
        self.seen.append((system, list(transcript)))
        if not self._replies:
            raise RuntimeError("The script has no more replies")
        return self._replies.pop(0)

    @classmethod
    def from_file(cls, path: Path) -> "ScriptedClient":
        """A JSON list of turns: {"text": ...} or {"tool_calls": [{"name": ..., "arguments": {...}}]}."""
        turns = json.loads(Path(path).read_text())
        return cls(
            [
                ModelTurn(text=t.get("text", ""), tool_calls=tuple(ToolCall(**c) for c in t.get("tool_calls", [])))
                for t in turns
            ],
            name=f"scripted:{Path(path).name}",
        )


def client_from_env() -> ModelClient:
    """The model named by FC_MODEL: `anthropic:<model>`, `openai:<base url>|<model>` or `scripted:<file>`."""
    spec = os.environ.get("FC_MODEL", f"anthropic:{DEFAULT_CLAUDE}")
    kind, _, rest = spec.partition(":")
    if kind == "anthropic":
        return ClaudeClient(model=rest or DEFAULT_CLAUDE)
    if kind == "openai":
        base_url, _, model = rest.partition("|")
        return OpenAICompatibleClient(base_url, model, api_key=os.environ.get("OPENAI_API_KEY"))
    if kind == "scripted":
        return ScriptedClient.from_file(Path(rest))
    raise ValueError(f"Unknown FC_MODEL {spec!r}")
