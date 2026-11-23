"""Records what the agent sends for the demo script's first two questions, as
Server-Sent Events, into catalog/fixtures. The app's tests replay them as a
stand-in agent. tests/test_recordings.py fails if the agent's output drifts
from what is recorded; run this to record again after an intended change.
"""

from pathlib import Path

from finance_agent.agent import Agent
from finance_agent.catalog import load_catalog
from finance_agent.model import ScriptedClient
from finance_agent.server import sse_events
from finance_agent.warehouse import Warehouse

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "agent" / "demo" / "script.json"
FIXTURES = ROOT / "catalog" / "fixtures"


def recordings() -> dict[str, str]:
    agent = Agent(Warehouse(), load_catalog(), ScriptedClient.from_file(SCRIPT))
    apple = "".join(sse_events(agent.answer("How is Apple doing?")))
    month = "".join(
        sse_events(
            agent.act(
                {"action": {"name": "set_range", "surfaceId": "answer-1", "context": {"result": "/r1", "days": 30}}}
            )
        )
    )
    return {"apple-answer.sse": apple, "apple-one-month.sse": month}


if __name__ == "__main__":
    for name, text in recordings().items():
        (FIXTURES / name).write_text(text)
        print("wrote", name)
