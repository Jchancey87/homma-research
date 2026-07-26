# ADR 0002: Decouple LLM Prompts, Transport, and Analyzers

## Status
Accepted

## Context
`llm_client.py` in `backend/llm/llm_client.py` was a 1,069-line monolithic module housing 13 unrelated LLM interaction patterns (continuation analysis, sentiment, catalyst scoring, PIPE analysis, reflection, etc.).

Prompts (over 500 lines of system prompt text), API transport client creation (`OpenAI`), model routing (fast vs deep), business logic gates, response parsing, and error fallback were all interleaved in a single file without dependency injection.

## Decision
We decouple the LLM subsystem into three distinct layers:
1. **Transport Layer (`backend/llm/transport.py`)**: Deep `LLMTransport` class hiding API client instantiation, retry logic, and model routing. Supports dependency injection of mock clients for zero-network unit testing.
2. **Prompt Layer (`backend/llm/prompts.py`)**: Pure Python prompt builder functions returning `(system_prompt, user_prompt)` tuples. Tested independently of API network calls.
3. **Analyzer Layer (`backend/llm/analyzers/`)**: Dedicated domain analyzers (`continuation_analyzer.py`, `sentiment_analyzer.py`, `reflection_analyzer.py`, `catalyst_analyzer.py`) accepting an injected `LLMTransport` and returning structured domain objects.
4. **Compatibility Facade (`backend/llm/llm_client.py`)**: Thin 30-line facade delegating legacy function calls to the new analyzers, preserving 100% backward compatibility.

## Consequences
### Positive
- Prompts can be inspected, versioned, and unit-tested as pure string functions.
- All 13 LLM capabilities can be tested in isolation using mock transport implementations.
- Zero import breakage across existing jobs, tasks, and routers.

### Negative / Trade-offs
- Adds a layered file structure under `backend/llm/` (`transport.py`, `prompts.py`, `analyzers/`).
