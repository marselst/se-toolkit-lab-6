# Task 1 plan: Call an LLM from Code

## Goal
Build `agent.py` that takes a question, calls an OpenAI-compatible LLM API, and prints a single JSON object:

- `answer`: the model response
- `tool_calls`: an empty list

All non-JSON output goes to stderr.

## Config
- `LLM_MODEL` (optional, default `meta-llama/llama-3.3-70b-instruct:free`)

## Implementation sketch
1. Parse question from `sys.argv[1]`, exit nonzero if missing.
2. Call the chat completions API (OpenAI-compatible) with a minimal system prompt + user question.
3. Enforce a timeout (≤60s).
4. Extract answer from `choices[0].message.content`.
5. Print JSON: `{"answer": ..., "tool_calls": []}`.
