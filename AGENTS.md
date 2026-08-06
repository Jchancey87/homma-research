# Agent Guidelines (AGENTS.md) 🤖

> **What is this project?** A FastAPI + Next.js trading-research platform tracking real-time gainers, alerts, and analytics via the Schwab API.

---

## Core Rules

### Communication
- Responses: brief, direct, actionable. No filler.
- File links: clickable Markdown with `file://` scheme — e.g., `[main.py](file:///backend/fastapi_app/main.py)`.
- Internal docs / devlogs / subagent prompts / tool metadata: telegraphic caveman style (omit articles, helping verbs, preambles). User-facing messages stay readable.

### Code Edits
- `replace_file_content` → single contiguous block. `multi_replace_file_content` → multiple separate blocks. Never run both in parallel on the same file.
- Do not read entire files >200 lines when a targeted chunk suffices.
- Scratchpads go in `scratch/` or `backend/scratch/` only.
- Run targeted tests/lints immediately after edits. Full suite only before commit/push/deploy.

### Comments & Docs
- Never modify or delete existing comments, docstrings, or documentation unless explicitly asked.

### Memory (`AGENT_MEMORY.md`)
- **Session start:** define current goals, assumptions, and scope in the `session` section.
- **Session end:** merge verified decisions into the `main` section. Prune stale rules. Heavy logs → `AGENT_MEMORY_HISTORY.md`.

---

## Project Map

| File / Dir | Purpose |
|---|---|
| `README.md` | Project overview |
| `CONTEXT.md` | Domain glossary & ubiquitous language |
| `docs/ARCHITECTURE.md` | System architecture |
| `docs/DEVOPS_GUIDE.md` | Deployment & ops |
| `docs/adr/` | Architectural Decision Records |
| `devlogs.md` | State tracker (chronological log) |
| `AGENT_MEMORY.md` | Active agent adaptations & decisions |
| `pocket-data/issue-setup.md` | Issue workflow setup |
| `handoffs/` | Agent handoff notes |

---

## Agent Skills & Conventions

| Topic | Detail file |
|---|---|
| Backend router / service rules | [docs/agents/backend-conventions.md](file:///home/jackc/projects/homma-research/docs/agents/backend-conventions.md) |
| GitHub issue tracker usage | [docs/agents/issue-tracker.md](file:///home/jackc/projects/homma-research/docs/agents/issue-tracker.md) |
| Triage label vocabulary | [docs/agents/triage-labels.md](file:///home/jackc/projects/homma-research/docs/agents/triage-labels.md) |
| Domain docs & ADR reading protocol | [docs/agents/domain.md](file:///home/jackc/projects/homma-research/docs/agents/domain.md) |
