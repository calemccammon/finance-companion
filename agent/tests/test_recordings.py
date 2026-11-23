"""The recorded streams the app's tests replay are what the agent sends today."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from record_streams import FIXTURES, recordings


def test_the_recordings_match_the_agent():
    for name, text in recordings().items():
        assert (FIXTURES / name).read_text() == text, f"{name} is stale: run scripts/record_streams.py"
