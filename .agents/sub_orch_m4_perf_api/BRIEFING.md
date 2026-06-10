# BRIEFING — 2026-06-05T21:49:36-05:00

## Mission
Calculate forward returns and excursion metrics on-the-fly in the daily summary alert API endpoint and verify implementation with unit tests.

## 🔒 My Identity
- Archetype: teamwork_preview_orchestrator
- Roles: orchestrator, user_liaison, human_reporter, successor
- Working directory: /home/jackc/projects/homma-research/.agents/sub_orch_m4_perf_api
- Original parent: main agent
- Original parent conversation ID: ee5209ca-ae81-4277-8b41-6d589db91ba3

## 🔒 My Workflow
- **Pattern**: Project (Sub-orchestrator)
- **Scope document**: /home/jackc/projects/homma-research/.agents/sub_orch_m4_perf_api/SCOPE.md
1. **Decompose**: Task fits a single Explorer -> Worker -> Reviewer cycle. We will run it directly as a single iteration loop.
2. **Dispatch & Execute** (pick ONE):
   - **Direct (iteration loop)**: Spawn Explorer(s) -> Spawn Worker -> Spawn Reviewer(s) + Challenger(s) -> Spawn Auditor -> Gate.
   - **Delegate (sub-orchestrator)**: N/A
3. **On failure** (in this order):
   - Retry: nudge stuck agent or re-send task
   - Replace: spawn fresh agent with partial progress
   - Skip: proceed without (only if non-critical)
   - Redistribute: split stuck agent's remaining work
   - Redesign: re-partition decomposition
   - Escalate: report to parent (sub-orchestrators only, last resort)
4. **Succession**: Self-succeed at 16 spawns, write handoff.md, spawn successor.
- **Work items**:
  1. Explore current file and setup strategy [in-progress]
  2. Implement changes in alerts.py [pending]
  3. Review implementation [pending]
  4. Perform adversarial tests / checks [pending]
  5. Audit integrity [pending]
- **Current phase**: 1
- **Current focus**: Explorer analysis.

## 🔒 Key Constraints
- Calculate forward returns at 1m, 3m, 5m, 15m using closest available preceding candle close in the 15-minute window or null if none.
- Calculate MFE and MAE over all candles in the 15m window.
- Do not write, modify, or create source code files directly.
- Do not run builds or tests directly.
- Never reuse a subagent after it has delivered its handoff.

## Current Parent
- Conversation ID: ee5209ca-ae81-4277-8b41-6d589db91ba3
- Updated: not yet

## Key Decisions Made
- Confirmed task fits a single Explorer -> Worker -> Reviewer cycle.

## Team Roster
| Agent | Type | Work Item | Status | Conv ID |
|-------|------|-----------|--------|---------|
| explorer_1 | teamwork_preview_explorer | Explore current file and schema | in-progress | bc8688c4-50b0-481f-919d-9a5f3f60036e |

## Succession Status
- Succession required: no
- Spawn count: 1 / 16
- Pending subagents: none
- Predecessor: none
- Successor: not yet spawned

## Active Timers
- Heartbeat cron: 54e86b04-08ab-40a6-b59d-512872e9e62d/task-21
- Safety timer: none

## Artifact Index
- /home/jackc/projects/homma-research/.agents/sub_orch_m4_perf_api/SCOPE.md — Scope requirements
- /home/jackc/projects/homma-research/.agents/sub_orch_m4_perf_api/ORIGINAL_REQUEST.md — Verbatim user request
- /home/jackc/projects/homma-research/.agents/sub_orch_m4_perf_api/progress.md — Heartbeat and step tracking
