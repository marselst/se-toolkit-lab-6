# Task 2 Plan: The Documentation Agent

## Goal
Превратить чат-бота из Task 1 в агента с инструментами `read_file` и `list_files` для навигации по wiki проекта.

## Архитектура

### Tool schemas
Определю две функции как схемы для function calling:

1. **`read_file(path: str)`** — читает файл из репозитория
   - Принимает относительный путь от корня проекта
   - Возвращает содержимое файла или сообщение об ошибке
   - Проверка безопасности: запрет `../` для выхода за пределы проекта

2. **`list_files(path: str)`** —列出目录内容
   - Принимает относительный путь к директории
   - Возвращает список файлов через newline
   - Проверка безопасности: та же логика против `../`

### Agentic loop
Цикл будет работать так:

1. Отправить вопрос + system prompt + tool definitions в LLM
2. Если LLM вернул `tool_calls`:
   - Выполнить каждый инструмент
   - Добавить результаты как сообщения с ролью `tool`
   - Повторить шаг 1
3. Если LLM вернул текстовый ответ (без tool calls):
   - Это финальный ответ
   - Извлечь `answer` и `source`
   - Вывести JSON и завершить
4. Лимит: максимум 10 tool calls за один запрос

### Path security
Для защиты от чтения файлов вне проекта:

```python
def is_safe_path(base_path: Path, user_path: Path) -> bool:
    """Проверить, что user_path находится внутри base_path."""
    try:
        # Разрешить относительные пути
        resolved = (base_path / user_path).resolve()
        return resolved.is_relative_to(base_path)
    except (ValueError, TypeError):
        return False
```

Также явная проверка на `..` в пути.

### System prompt strategy
System prompt будет инструктировать LLM:

1. Использовать `list_files` для обнаружения файлов wiki
2. Использовать `read_file` для чтения содержимого
3. Всегда указывать `source` в формате `path/to/file.md#section-anchor`
4. Не выдумывать источники — использовать только реальные файлы

### Data flow
```
User question
     │
     ▼
┌─────────────────┐
│  Send to LLM    │
│  + tool schemas │
└─────────────────┘
     │
     ▼
  tool_calls?
     │
  ┌──┴──┐
  │ yes │────────────────────────┐
  └─────┘                        │
     │                           │
     ▼                           ▼
┌─────────────┐           ┌──────────────┐
│ Execute     │           │ No tool calls│
│ tools       │           │ → final answer│
└─────────────┘           └──────────────┘
     │                           │
     ▼                           ▼
┌─────────────┐           ┌──────────────┐
│ Append as   │           │ Extract      │
│ tool role   │           │ answer+source│
│ messages    │           └──────────────┘
└─────────────┘                  │
     │                           ▼
     │                    ┌──────────────┐
     └───────────────────▶│ Output JSON  │
                          └──────────────┘
```

## Тесты
Добавлю 2 регрессионных теста:

1. **"How do you resolve a merge conflict?"**
   - Ожидается: `read_file` в `tool_calls`
   - Ожидается: `wiki/git-workflow.md` в `source`

2. **"What files are in the wiki?"**
   - Ожидается: `list_files` в `tool_calls`

## Риски
- LLM может некорректно форматировать tool calls → нужна обработка ошибок
- Таймауты API → увеличить timeout или добавить retry
- LLM может забыть указать source → добавить валидацию в system prompt
