## 2026-06-06T02:50:14Z
Context: We are building a comprehensive opaque-box E2E test suite (>= 49 tests across Tiers 1-4) for real-time momentum alert optimizations and Alert Journal upgrade.
Task: Set up the E2E test infrastructure, write TEST_INFRA.md at the project root, and write the test cases under backend/tests/e2e/test_cases.py.
Your working directory is: /home/jackc/projects/homma-research/.agents/worker_e2e_setup
Your parent is the E2E Testing Orchestrator (Conversation ID: f4572c1e-ae4c-47e1-921f-d3723d617215).

Key Deliverables:
1. TEST_INFRA.md: Document E2E test philosophy, feature inventory, test architecture, and setup instructions. Formatted according to the template in the orchestrator instructions.
2. Test Runner & Mocking Engine: Write test helpers to mock the Schwab streaming API quote messages, capture Redis pub/sub broadcasts, capture Celery task dispatches, and seed stock fundamentals & watchlist in PostgreSQL.
3. Tiers 1-4 Test Suite: Deliver at least 49 tests covering:
   - Tier 1: Feature Coverage (>= 20 tests total, >= 5 per feature)
     * Feature 1: Trigger quality optimizations (R1: body-close HOD, TOD volume, ATR-based VWAP, post-halt suppression) - >= 7 tests
     * Feature 2: Actionable Telegram Alerts (R2) - >= 6 tests
     * Feature 3: Performance & Expectancy Feedback Loop (R3: forward returns, excursions, frontend scorecard UI logic) - >= 7 tests
   - Tier 2: Boundary & Corner Cases (>= 20 tests total, >= 5 per feature)
     * Feature 1 (R1) - >= 7 tests
     * Feature 2 (R2) - >= 6 tests
     * Feature 3 (R3) - >= 7 tests
   - Tier 3: Cross-Feature Combinations (>= 4 tests total)
   - Tier 4: Real-world Application Scenarios (>= 5 tests total)
4. Verify all tests execute and compile. Note: since the actual implementation of the alert optimization features and UI scorecard has not occurred yet, it is expected that the assertions in the tests will fail. The goal is to make the tests compile, run, and fail/pass cleanly (i.e. no syntax or imports errors, they fail on the assertions of the unimplemented logic).

Mandatory Integrity Warning:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Specifications:
- Read requirements from /home/jackc/projects/homma-research/.agents/ORIGINAL_REQUEST.md.
- Read scope from /home/jackc/projects/homma-research/.agents/sub_orch_e2e/SCOPE.md.
- Read code layout from /home/jackc/projects/homma-research/PROJECT.md.
- Read existing backend test setup from /home/jackc/projects/homma-research/backend/tests/conftest.py.
- Use pytest to write these E2E tests under backend/tests/e2e/test_cases.py so they leverage the session database pool and HTTPX client.
- When done, run pytest to run the E2E tests (you can filter by file or tags if needed) and check that they all execute. Include the command run and output in your handoff report.
