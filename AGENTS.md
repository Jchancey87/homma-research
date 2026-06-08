# Agent Guidelines (AGENTS.md) 🤖
Read completely on startup before beginning any task.

## 📜 Rules of Engagement

### 1. Style & Integrity
* **Documentation:** Never modify/delete existing comments, docstrings, or docs unless explicitly requested. Preserve original comments.
* **Links:** Format all file/directory references as clickable Markdown links using absolute paths with the `file://` scheme (e.g., `[main.py](file:///backend/fastapi_app/main.py)`).
* **Communication:** Keep responses to the user brief, direct, and actionable.

### 2. File Modifying Best Practices
* **Edits:** Use `replace_file_content` for single contiguous line blocks. Use `multi_replace_file_content` for multiple separate blocks. *Never run these in parallel on the same file.*
* **Scratchpads:** Store temporary scripts, test queries, or debug logs only in `scratch/` or `backend/scratch/`.
* **Links & Paths:** Use the `sigmap` MCP tool to locate files. When referencing files/directories in responses, always format them as clickable Markdown links using absolute paths with the `file://` scheme (e.g., `[main.py](file:///backend/fastapi_app/main.py)`).
* **Communication:** Keep responses to the user brief, direct, and actionable.

### 3. Tooling & Token Efficiency
* **Search:** Prefer `rg` over `grep`. Exclude `node_modules`, `.venv`, `.git`, `dist`, `build`, and lockfiles from broad searches unless explicitly targeted.
* **Tokens:** Do not read entire files >200 lines if chunks suffice. Use atomic search-and-replace instead of rewriting unchanged code blocks.
* **QA:** Use `&&` for short related command chains. Use quiet flags (`-q`, `-s`) unless debugging failures. Run local tests and lints after modifying code.

### 4. Memory Management (AGENT_MEMORY.md)
* **Fork:** At session start, define current goals, assumptions, and scope in the session section.
* **Merge:** At session end, merge verified, persistent architectural/design decisions into the main section.
* **Prune/Archive:** Actively delete stale rules/completed notes. Move heavy chronological logs to `AGENT_MEMORY_HISTORY.md`.

## 📂 Key Files Reference
* `README.md` / `docs/ARCHITECTURE.md` / `docs/DEVOPS_GUIDE.md`
* `devlogs.md` (State tracker) | `AGENT_MEMORY.md` (Active adaptations)
* `pocket-data/issue-setup.md` (GitHub issue workflows) | `handoffs/` (Historical handoffs)

## 🏗️ Active Focus
- [ ] Review current database schema & verify Schwab token retrieval.
- [ ] Investigate user-requested updates.
- [ ] Update `devlogs.md` and `AGENT_MEMORY.md` dynamically.
