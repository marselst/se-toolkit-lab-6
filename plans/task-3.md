# Task 3 Plan: The System Agent

## Goal
Добавить инструмент `query_api` для взаимодействия с backend API и обновить агента для ответа на вопросы о системе и данных.

## Архитектура

### Tool schema: query_api
Новый инструмент для вызовов к backend API:

```python
{
    "type": "function",
    "function": {
        "name": "query_api",
        "description": "Call the deployed backend API to get system information or query data.",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
                "path": {"type": "string", "description": "API path (e.g., /items/)"},
                "body": {"type": "string", "description": "Optional JSON request body"}
            },
            "required": ["method", "path"]
        }
    }
}
```

### Аутентификация
- Использовать `LMS_API_KEY` из `.env.docker.secret`
- Передавать в заголовке `X-API-Key` или `Authorization: Bearer ...`
- URL API: `AGENT_API_BASE_URL` (по умолчанию `http://localhost:42002`)

**Важно:** Не путать `LMS_API_KEY` (backend) с `LLM_API_KEY` (LLM провайдер).

### Реализация query_api
```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Call the deployed backend API.
    
    Returns JSON string with status_code and body.
    """
    api_base = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")
    
    url = f"{api_base}{path}"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    # Выполнить запрос и вернуть JSON с status_code и body
```

### Обновление system prompt
Добавить инструкции для LLM:

1. **wiki вопросы** → использовать `list_files` и `read_file`
2. **системные факты** (фреймворк, порты, статус коды) → использовать `read_file` для чтения кода
3. **вопросы о данных** (количество элементов, оценки) → использовать `query_api`

Пример system prompt:
```
When answering questions:
- For wiki/documentation questions: use list_files and read_file
- For system facts (framework, ports, status codes): read the source code with read_file
- For data queries (item count, scores, analytics): use query_api
- Always include a source field when referencing documentation
```

### Agentic loop
Остаётся без изменений — просто добавляется третий инструмент в список доступных.

### Environment variables
| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for query_api (default: http://localhost:42002) | Optional |

**Важно:** Все значения читаются из environment variables, не hardcode!

## Тесты
Добавлю 2 регрессионных теста:

1. **"What framework does the backend use?"** → ожидается `read_file` в tool_calls
2. **"How many items are in the database?"** → ожидается `query_api` в tool_calls

## Benchmark workflow
1. Запустить `uv run run_eval.py`
2. Записать initial score
3. Для каждого failing question:
   - Прочитать feedback
   - Исправить agent (tool descriptions, system prompt)
   - Re-run
4. Итерировать до прохождения

## Implementation Status

**Completed:**
- ✅ `query_api` tool implemented with full HTTP method support
- ✅ Authentication via `LMS_API_KEY` from `.env.docker.secret`
- ✅ Error handling for connection errors, timeouts, invalid JSON
- ✅ System prompt updated with tool selection strategy
- ✅ Source extraction extended for API endpoints
- ✅ `load_env()` loads both `.env.agent.secret` and `.env.docker.secret`

**Tests Added:**
- ✅ `test_agent_backend_framework_uses_read_file` — expects `read_file` tool
- ✅ `test_agent_database_items_uses_query_api` — expects `query_api` tool

**Benchmark Status:**
Backend (Docker) is required for full benchmark testing. The agent is ready for evaluation once the backend is running on port 42002.

To run the benchmark:
```bash
# Start the backend (requires Docker)
docker compose up -d

# Run evaluation
uv run run_eval.py
```

## Risks
- LLM может не знать, когда использовать query_api vs read_file → нужны чёткие инструкции
- API может вернуть ошибку → нужна обработка ошибок в query_api
- Hardcoded значения → провал на autochecker → читать только из env vars

**Mitigation:**
- ✅ Clear tool descriptions in TOOL_DEFINITIONS
- ✅ System prompt explicitly categorizes question types
- ✅ All config values read from environment variables
