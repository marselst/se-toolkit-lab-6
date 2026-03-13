import json
import os
import subprocess
import sys

import pytest


def test_agent_outputs_json_structure():
    """Run agent.py and assert the output is valid JSON with the required keys."""

    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY is not set; skipping LLM integration test")

    proc = subprocess.run(
        [sys.executable, "agent.py", "What does REST stand for?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, f"agent.py exited non-zero: {proc.stderr}"

    data = json.loads(proc.stdout.strip())
    assert "answer" in data
    assert "tool_calls" in data
    assert isinstance(data["tool_calls"], list)
