"""The language model, behind one small interface.

The agent keeps the conversation in its own neutral shape and each client
translates it for one API: any OpenAI-compatible endpoint (a local Ollama,
for one), or a script of replies for tests.
"""

import json
import os
import uuid
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


# --- OpenAI-compatible ------------------------------------------------------

DEFAULT_MODEL = "openai:http://127.0.0.1:11434/v1|qwen3:8b"


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
                # A turn with nothing in it cannot be sent (Ollama refuses its null content).
                if not text and not calls:
                    continue
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
    """The model named by FC_MODEL: `openai:<base url>|<model>` or `scripted:<file>`.
    Without it, qwen3:8b on a local Ollama."""
    spec = os.environ.get("FC_MODEL", DEFAULT_MODEL)
    kind, _, rest = spec.partition(":")
    if kind == "openai":
        base_url, _, model = rest.partition("|")
        return OpenAICompatibleClient(base_url, model, api_key=os.environ.get("OPENAI_API_KEY"))
    if kind == "scripted":
        return ScriptedClient.from_file(Path(rest))
    raise ValueError(f"Unknown FC_MODEL {spec!r}")
