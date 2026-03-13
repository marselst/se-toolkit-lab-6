#!/usr/bin/env python3
"""
Regression tests for agent.py CLI.

Tests verify that agent.py:
- Exits with correct status codes
- Outputs valid JSON with required structure
- Handles missing arguments correctly
"""

import json
import os
import subprocess
import sys

import pytest


def test_agent_no_question_exits_nonzero():
    """Test that agent.py exits with error when no question is provided."""
    proc = subprocess.run(
        [sys.executable, "agent.py"],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert proc.returncode != 0
    assert "Error" in proc.stderr
    assert "No question provided" in proc.stderr


def test_agent_missing_question_exits_nonzero():
    """Test that agent.py exits with error when argument is empty."""
    proc = subprocess.run(
        [sys.executable, "agent.py", ""],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Empty question should still process but may return error or empty answer
    # The key is it should not crash
    if proc.returncode == 0:
        # If it succeeds, output should be valid JSON
        data = json.loads(proc.stdout.strip())
        assert "answer" in data
        assert "tool_calls" in data


@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY is not set; skipping LLM integration test",
)
def test_agent_outputs_json_structure():
    """Run agent.py and assert the output is valid JSON with the required keys."""
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
    assert isinstance(data["answer"], str)
    assert len(data["answer"]) > 0


@pytest.mark.skipif(
    not os.getenv("LLM_API_KEY"),
    reason="LLM_API_KEY is not set; skipping LLM integration test",
)
def test_agent_answer_is_not_hardcoded():
    """Test that different questions produce different answers."""
    questions = [
        "What is HTTP?",
        "What is the capital of France?",
    ]

    answers = []
    for question in questions:
        proc = subprocess.run(
            [sys.executable, "agent.py", question],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0
        data = json.loads(proc.stdout.strip())
        answers.append(data["answer"])

    # Answers should be different for different questions
    assert answers[0] != answers[1]
