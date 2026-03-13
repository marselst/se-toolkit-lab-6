#!/usr/bin/env python3
"""
Lab assistant agent CLI with documentation tools.

Takes a question as command-line argument, calls an OpenAI-compatible LLM API,
and prints a JSON object with the answer, source, and tool_calls.

Usage:
    uv run agent.py "<question>"

Output:
    JSON: {"answer": "...", "source": "...", "tool_calls": [...]}

All non-JSON output goes to stderr.
"""

import json
import os
import re
import sys
from pathlib import Path

import httpx

# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()


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


def is_safe_path(user_path: str) -> bool:
    """
    Check if the user-provided path is safe (doesn't escape project directory).
    
    Returns False if path contains '..' or resolves outside PROJECT_ROOT.
    """
    # Reject paths with .. components
    if ".." in user_path.split("/") or ".." in user_path.split("\\"):
        return False
    
    # Resolve the full path and ensure it's within PROJECT_ROOT
    try:
        full_path = (PROJECT_ROOT / user_path).resolve()
        return full_path.is_relative_to(PROJECT_ROOT)
    except (ValueError, TypeError):
        return False


def read_file(path: str) -> str:
    """
    Read a file from the project repository.
    
    Parameters:
        path (str): Relative path from project root.
    
    Returns:
        File contents as a string, or an error message if the file doesn't exist.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is not allowed (security restriction)"
    
    file_path = PROJECT_ROOT / path
    
    if not file_path.exists():
        return f"Error: File '{path}' does not exist"
    
    if not file_path.is_file():
        return f"Error: '{path}' is not a file"
    
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        return f"Error: Cannot read '{path}' - not a text file"
    except PermissionError:
        return f"Error: Permission denied reading '{path}'"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.
    
    Parameters:
        path (str): Relative directory path from project root.
    
    Returns:
        Newline-separated listing of entries, or an error message.
    """
    if not is_safe_path(path):
        return f"Error: Access denied - path '{path}' is not allowed (security restriction)"
    
    dir_path = PROJECT_ROOT / path
    
    if not dir_path.exists():
        return f"Error: Directory '{path}' does not exist"
    
    if not dir_path.is_dir():
        return f"Error: '{path}' is not a directory"
    
    try:
        entries = sorted(os.listdir(dir_path))
        return "\n".join(entries)
    except PermissionError:
        return f"Error: Permission denied listing '{path}'"


# Tool definitions for LLM function calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to read documentation files in the wiki/ directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to discover what files exist in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# Map tool names to actual functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
}

SYSTEM_PROMPT = """You are a helpful lab assistant that answers questions about the project using its documentation.

You have access to two tools:
1. `list_files` - List files in a directory
2. `read_file` - Read the contents of a file

When answering questions:
1. First use `list_files` to discover relevant files in the wiki/ directory
2. Then use `read_file` to read the contents of files that might contain the answer
3. Always include a `source` field in your final answer with the format: `path/to/file.md#section-anchor`
4. The section anchor should be the markdown heading that contains the answer (lowercase, hyphens instead of spaces)
5. Do not make up sources - only reference files you have actually read
6. Be concise and direct in your answers

If you cannot find the answer in the documentation, say so honestly.
"""


def execute_tool_call(tool_call) -> dict:
    """
    Execute a single tool call and return the result.
    
    Returns a dict with 'tool', 'args', and 'result' keys.
    """
    tool_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    
    print(f"[DEBUG] Executing tool: {tool_name} with args: {args}", file=sys.stderr)
    
    if tool_name not in TOOL_FUNCTIONS:
        result = f"Error: Unknown tool '{tool_name}'"
    else:
        func = TOOL_FUNCTIONS[tool_name]
        try:
            result = func(**args)
        except Exception as e:
            result = f"Error: {type(e).__name__}: {e}"
    
    return {
        "tool": tool_name,
        "args": args,
        "result": result
    }


def extract_source_from_answer(answer: str, messages: list) -> str:
    """
    Try to extract a source reference from the answer or messages.
    
    Looks for patterns like wiki/filename.md or wiki/filename.md#section
    """
    # Pattern to match wiki file references
    pattern = r'wiki/[\w\-]+\.md(?:#[\w\-]+)?'
    
    # Search in the answer first
    match = re.search(pattern, answer, re.IGNORECASE)
    if match:
        source = match.group(0).lower()
        # Ensure anchor is lowercase
        if '#' in source:
            path, anchor = source.split('#', 1)
            return f"{path}#{anchor.lower()}"
        return source
    
    # Search in tool results
    for msg in messages:
        if msg.get("role") == "tool" and "content" in msg:
            match = re.search(pattern, msg["content"], re.IGNORECASE)
            if match:
                source = match.group(0).lower()
                if '#' in source:
                    path, anchor = source.split('#', 1)
                    return f"{path}#{anchor.lower()}"
                return source
    
    return "wiki/unknown.md"


def call_llm(messages: list, api_key: str, api_base: str, model: str) -> dict:
    """
    Call the LLM API with the given messages.
    
    Returns the parsed response data.
    """
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": TOOL_DEFINITIONS,
            },
        )
        response.raise_for_status()
        return response.json()


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

    # Initialize messages with system prompt and user question
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Track all tool calls
    all_tool_calls = []
    tool_call_count = 0

    # Agentic loop
    while tool_call_count < MAX_TOOL_CALLS:
        print(f"[DEBUG] Agentic loop iteration {tool_call_count + 1}", file=sys.stderr)
        
        try:
            data = call_llm(messages, api_key, api_base, model)
        except httpx.TimeoutException:
            print("Error: Request timed out after 60 seconds", file=sys.stderr)
            sys.exit(1)
        except httpx.HTTPError as e:
            print(f"Error: HTTP request failed: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError:
            print("Error: Invalid JSON response from API", file=sys.stderr)
            sys.exit(1)

        # Extract message from response
        try:
            response_message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            print("Error: Unexpected API response format", file=sys.stderr)
            sys.exit(1)

        # Check for tool calls
        tool_calls = response_message.get("tool_calls")
        
        if not tool_calls:
            # No tool calls - this is the final answer
            print("[DEBUG] No tool calls, extracting final answer", file=sys.stderr)
            answer = response_message.get("content", "")
            
            # Extract source from answer
            source = extract_source_from_answer(answer, messages)
            
            # Output result as JSON
            result = {
                "answer": answer,
                "source": source,
                "tool_calls": all_tool_calls
            }
            print(json.dumps(result, ensure_ascii=False))
            return

        # Execute tool calls
        print(f"[DEBUG] Processing {len(tool_calls)} tool call(s)", file=sys.stderr)
        
        # Add assistant's message with tool calls to history
        messages.append(response_message)
        
        for tool_call in tool_calls:
            tool_call_count += 1
            
            if tool_call_count > MAX_TOOL_CALLS:
                print(f"[DEBUG] Reached max tool calls limit ({MAX_TOOL_CALLS})", file=sys.stderr)
                break
            
            # Execute the tool
            tool_result = execute_tool_call(tool_call)
            all_tool_calls.append(tool_result)
            
            # Add tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": tool_result["result"],
            })
            
            print(f"[DEBUG] Tool result: {tool_result['result'][:100]}...", file=sys.stderr)

    # Reached max tool calls - provide whatever answer we have
    print("[DEBUG] Reached maximum tool calls, generating final answer", file=sys.stderr)
    
    # Ask LLM to provide final answer based on collected information
    messages.append({
        "role": "system",
        "content": "You have reached the maximum number of tool calls. Please provide your best answer based on the information you have gathered. Include a source reference."
    })
    
    try:
        data = call_llm(messages, api_key, api_base, model)
        response_message = data["choices"][0]["message"]
        answer = response_message.get("content", "")
        source = extract_source_from_answer(answer, messages)
    except Exception:
        # Fallback: use last known information
        answer = "Unable to complete the request within tool call limits."
        source = "wiki/unknown.md"
    
    result = {
        "answer": answer,
        "source": source,
        "tool_calls": all_tool_calls
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
