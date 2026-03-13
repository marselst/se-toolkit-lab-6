#!/usr/bin/env python3
"""
Lab assistant agent CLI.

Takes a question as command-line argument, calls an OpenAI-compatible LLM API,
and prints a JSON object with the answer and tool_calls.

Usage:
    uv run agent.py "<question>"

Output:
    JSON: {"answer": "...", "tool_calls": []}
    
All non-JSON output goes to stderr.
"""

import json
import os
import sys
from pathlib import Path

import httpx


def load_env():
    """Load environment variables from .env.agent.secret if it exists."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()

    # Parse question from command line
    if len(sys.argv) < 2:
        print("Error: No question provided. Usage: agent.py \"<question>\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Get configuration from environment
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE", "https://openrouter.ai/api/v1")
    model = os.getenv("LLM_MODEL", "meta-llama/llama-3.3-70b-instruct:free")

    if not api_key:
        print("Error: LLM_API_KEY not set. Please configure .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    # Call the LLM API
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a helpful lab assistant. Answer questions clearly and concisely.",
                        },
                        {"role": "user", "content": question},
                    ],
                },
            )
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        print("Error: Request timed out after 60 seconds", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPError as e:
        print(f"Error: HTTP request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON response from API", file=sys.stderr)
        sys.exit(1)

    # Extract answer from response
    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print("Error: Unexpected API response format", file=sys.stderr)
        sys.exit(1)

    # Output result as JSON
    result = {"answer": answer, "tool_calls": []}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
