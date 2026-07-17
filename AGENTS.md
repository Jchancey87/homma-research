# Agent Guidelines (AGENTS.md) 🤖
Read completely on startup before beginning any task.

## 📜 Rules of Engagement

### 1. Style & Formatting
* **Comments:** Never modify or delete existing comments, docstrings, or documentation unless explicitly requested. Preserve original intent.
* **Links:** Format all file/directory references as clickable Markdown links using absolute paths with the `file://` scheme (e.g., `[main.py](file:///backend/fastapi_app/main.py)`).
* **Communication:** Keep responses to the user brief, direct, and actionable. No conversational fluff.
* **Caveman Skill:** Use ultra-compressed, telegraphic writing style for all internal documentation, devlogs (e.g., [devlogs.md](file:///home/jackc/projects/homma-research/devlogs.md)), agent memory (e.g., [AGENT_MEMORY.md](file:///home/jackc/projects/homma-research/AGENT_MEMORY.md)), scratchpad notes, subagent definitions/prompts, inter-agent messages, scheduled notifications, and tool metadata (descriptions/summaries). Omit articles, helping verbs, preambles, and filler words. Focus purely on technical facts (nouns, main verbs, numeric values). User-facing messages must remain readable and standard.


### 2. File Operations & Code Modification
* **Edits:** Use `replace_file_content` for single contiguous blocks. Use `multi_replace_file_content` for separate blocks. *Never execute these in parallel on the same file.*
* **Scratchpads:** Store temporary scripts, test queries, or debug logs exclusively in `scratch/` or `backend/scratch/`.
* **Token Efficiency:** Do not read entire files >200 lines if targeted chunks suffice. Use atomic search-and-replace instead of rewriting entire unchanged code blocks.
* **QA:** Run targeted tests/lints immediately on modified code. Run full test suite only before commit/push/deploy.

### 3. Memory & Context Management (`AGENT_MEMORY.md`)
* **Session Start:** Locate files using `sigmap`. Define current goals, assumptions, and scope in the `session` section of `AGENT_MEMORY.md`.
* **Session End:** Merge verified, persistent architectural/design decisions into the `main` section.
* **Prune:** Actively delete stale rules. Move heavy chronological logs to `AGENT_MEMORY_HISTORY.md`.

## 📂 Project Map
* **Docs & Architecture:** `README.md` | `docs/ARCHITECTURE.md` | `docs/DEVOPS_GUIDE.md`
* **State & Memory:** `devlogs.md` (State tracker) | `AGENT_MEMORY.md` (Active adaptations)
* **Workflows:** `pocket-data/issue-setup.md` | `handoffs/`

### 4. Router Layer Rules (enforced by RFC-001)
* **Routers are thin.** A router endpoint may only do: (a) parse + validate input, (b) call one service function, (c) format the response or translate domain exceptions to HTTP errors.
* **No business logic in routers.** Indicator math, FILTER-aggregate SQL, MFE/MAE, win-rate categorization, group-by stats — all of this belongs in `services/`. If an endpoint exceeds ~30 lines, extract a service.
* **No raw SQL in routers.** Routers obtain a `db` via `Depends(get_db)` and pass it to a service. SQL strings live in `services/<name>_service.py` or `fastapi_app/db/<name>.py`.
* **No external API calls in routers.** Schwab, FMP, SEC, Massive, yfinance — accessed through `services/schwab_client.py` (the facade) or a dedicated `services/<source>_service.py`.
* **Analytics services own their own tests.** Pure transforms (no DB / no HTTP) get unit tests in `tests/test_<service>.py`. Integration tests in `tests/test_<router>.py` cover the HTTP surface only.
* **Reference implementation:** see [services/chart_data_service.py](file:///home/jackc/projects/homma-research/backend/services/chart_data_service.py), [services/alerts_analytics.py](file:///home/jackc/projects/homma-research/backend/services/alerts_analytics.py), [services/continuation_analytics.py](file:///home/jackc/projects/homma-research/backend/services/continuation_analytics.py).
