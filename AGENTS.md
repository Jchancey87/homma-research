# Agent Guidelines (AGENTS.md) 🤖
Read completely on startup before beginning any task.

## 📜 Rules of Engagement

### 1. Style & Formatting
* **Comments:** Never modify or delete existing comments, docstrings, or documentation unless explicitly requested. Preserve original intent.
* **Links:** Format all file/directory references as clickable Markdown links using absolute paths with the `file://` scheme (e.g., `[main.py](file:///backend/fastapi_app/main.py)`).
* **Communication:** Keep responses to the user brief, direct, and actionable. No conversational fluff.
* **Caveman Skill:** Use ultra-compressed, telegraphic writing style for all internal documentation, devlogs (e.g., [devlogs.md](file:///home/jackc/projects/homma-research/devlogs.md)), agent memory (e.g., [AGENT_MEMORY.md](file:///home/jackc/projects/homma-research/AGENT_MEMORY.md)), and scratchpad notes. Omit articles, helping verbs, preambles, and filler words. Focus purely on technical facts (nouns, main verbs, numeric values). User-facing messages must remain readable and standard.


### 2. File Operations & Code Modification
* **Edits:** Use `replace_file_content` for single contiguous blocks. Use `multi_replace_file_content` for separate blocks. *Never execute these in parallel on the same file.*
* **Scratchpads:** Store temporary scripts, test queries, or debug logs exclusively in `scratch/` or `backend/scratch/`.
* **Token Efficiency:** Do not read entire files >200 lines if targeted chunks suffice. Use atomic search-and-replace instead of rewriting entire unchanged code blocks.
* **QA:** Run local tests and lints immediately after modifying any code.

### 3. Memory & Context Management (`AGENT_MEMORY.md`)
* **Session Start:** Locate files using `sigmap`. Define current goals, assumptions, and scope in the `session` section of `AGENT_MEMORY.md`.
* **Session End:** Merge verified, persistent architectural/design decisions into the `main` section.
* **Prune:** Actively delete stale rules. Move heavy chronological logs to `AGENT_MEMORY_HISTORY.md`.

## 📂 Project Map
* **Docs & Architecture:** `README.md` | `docs/ARCHITECTURE.md` | `docs/DEVOPS_GUIDE.md`
* **State & Memory:** `devlogs.md` (State tracker) | `AGENT_MEMORY.md` (Active adaptations)
* **Workflows:** `pocket-data/issue-setup.md` | `handoffs/`
