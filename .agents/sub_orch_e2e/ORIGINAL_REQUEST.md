# Original User Request

## 2026-06-06T02:49:10Z

You are the E2E Testing Orchestrator.
Your working directory is: /home/jackc/projects/homma-research/.agents/sub_orch_e2e
Your parent is: ee5209ca-ae81-4277-8b41-6d589db91ba3.
Your mission is to design a comprehensive opaque-box E2E test suite derived from the requirements in /home/jackc/projects/homma-research/.agents/ORIGINAL_REQUEST.md.

Scope details:
- Create the test infrastructure, test runner, and test case format.
- Deliver at least 49 tests across Tiers 1-4:
  - Tier 1: Feature coverage (>= 20 tests total, >= 5 per feature)
  - Tier 2: Boundary & Corner Cases (>= 20 tests total, >= 5 per feature)
  - Tier 3: Cross-Feature Combinations (>= 4 tests total)
  - Tier 4: Real-world Application Scenarios (>= 5 tests total)
- Ensure all features (R1: body-close HOD, TOD volume, ATR-based VWAP, post-halt suppression; R2: Telegram alerts; R3: forward returns calculation and scorecard UI) are covered.
- Document your plan and progress in /home/jackc/projects/homma-research/.agents/sub_orch_e2e/progress.md.
- Write TEST_INFRA.md and test cases in the workspace. Note: as an orchestrator, you must NOT write code directly — you MUST spawn a worker to write the test runner and test cases!
- When the test suite is complete and all tests can execute and report status (they might fail initially because implementation isn't done yet, but the runner and test definitions must be fully functional), publish TEST_READY.md.
- Report back when TEST_READY.md is published.
