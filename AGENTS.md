# Agent Onboarding & Guidelines (`AGENTS.md`) 🤖

Welcome! This file acts as the primary orientation guide for all AI coding agents working in this repository. **Please read this document fully on startup before beginning any task.**

---

## 🚀 Welcome Routine (Do This First!)

When starting a session or a new task, perform the following steps to orient yourself:
1. **Check Git Status**: Run `git status` to see if there are any untracked or modified files.
2. **Check Logs / Recent Activity**: Review [devlogs.md](file:///home/jackc/projects/homma-research/devlogs.md) to understand recent modifications and status updates.
3. **Inspect Active Workspaces**: Locate the frontend/backend services and ensure they are running properly.

---

## 🛠️ Project Architecture Summary

This platform is a self-hosted trade journal and research platform designed for technical traders.

* **Backend**: Python 3.12, FastAPI (Asynchronous lifespan), PostgreSQL (TimescaleDB), Celery, Redis. Located in [backend/](file:///home/jackc/projects/homma-research/backend).
* **Frontend**: Next.js 14 (App Router), Tailwind CSS. Located in [frontend/](file:///home/jackc/projects/homma-research/frontend).
* **AI Engine**: Groq (Llama 3) for text reports, Gemini 1.5 for chart annotation and pattern recognition.
* **Integrations**: Schwab Trader API, FMP API, SEC EDGAR, finviz, yfinance.
* **Database**: TimescaleDB for high-frequency market data.

---

## 📜 Agent Guidelines & Rules of Engagement

To maintain code quality and prevent system drift, adhere strictly to the following rules:

### 1. Style & Integrity
* **Documentation & Comments**: Do not modify or delete existing comments, docstrings, or documentation unless explicitly requested. Always preserve the original author's comments.
* **Links**: When referring to files, directory structures, or code components in your responses, **always** format them as clickable Markdown links using the absolute path with the `file://` scheme.
  * *Example*: [backend/fastapi_app/main.py](file:///home/jackc/projects/homma-research/backend/fastapi_app/main.py)
* **Conciseness**: Keep your responses to the user brief, direct, and actionable.

### 2. File Modifying Best Practices
* **Contiguous Changes**: Use the `replace_file_content` tool for editing single contiguous blocks of lines.
* **Non-contiguous Changes**: Use the `multi_replace_file_content` tool when modifying multiple separate blocks in a single file. Do not run these tools in parallel for the same file.
* **Scratch Space**: Store temporary scripts, test queries, or debug logs in the [scratch/](file:///home/jackc/projects/homma-research/scratch/) directory or the [backend/scratch/](file:///home/jackc/projects/homma-research/backend/scratch/) directory.

### 3. Tooling, Efficiency & QA Directives
* **Tooling & Search**:
  * Prefer `rg` (ripgrep) over `grep` for text searches and file scanning.
  * Exclude `node_modules`, `.venv`, `.git`, `dist`, and `build` from broad directory listings and searches unless the task explicitly targets them.
  * Exclude lockfiles from broad searches unless working on dependencies, package resolution, or CI/debug issues.
* **Token & Context Efficiency**:
  * Avoid reading entire files over 200 lines when targeted ranges or chunks will answer the question.
  * Prefer atomic search-and-replace edits over rewriting unchanged code blocks.
* **Execution & Quality Assurance**:
  * Use `&&` for short related command chains when it reduces turn count; split commands when intermediate inspection is useful.
  * Use quiet flags like `-q` or `-s` when verbose output is unnecessary, but do not hide useful failure diagnostics.
  * After modifying code, run the relevant local tests and lint checks before finalizing.

---

## 📂 Key Files & Directories

* **Project Documentation**:
  * [README.md](file:///home/jackc/projects/homma-research/README.md) - General setup and commands.
  * [docs/ARCHITECTURE.md](file:///home/jackc/projects/homma-research/docs/ARCHITECTURE.md) - Detailed backend & database architecture.
  * [docs/DEVOPS_GUIDE.md](file:///home/jackc/projects/homma-research/docs/DEVOPS_GUIDE.md) - Hosting, deployment, and service management.
  * [devlogs.md](file:///home/jackc/projects/homma-research/devlogs.md) - Chronological development logs and state tracker.
* **Data & Authority Mapping**:
  * [pocket-data/issue-setup.md](file:///home/jackc/projects/homma-research/pocket-data/issue-setup.md) - Pocket data alignment and GitHub issue flows.
  * [handoffs/](file:///home/jackc/projects/homma-research/handoffs/) - Historical coding agent handoff documents.

---

## 🏗️ Active Tasks & Focus Areas
*(To be updated dynamically by the user or agents as tasks evolve.)*

- [ ] Review current database schema and verify Schwab token retrieval processes.
- [ ] Investigate issues or feature updates requested by the user.
- [ ] Keep [devlogs.md](file:///home/jackc/projects/homma-research/devlogs.md) updated as changes are made.
