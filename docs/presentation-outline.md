# TestSphere.AI - Presentation Outline

## 1. Title
**TestSphere.AI**
Change-Impact Test Selector for Mobile Banking

## 2. Real-world Problem
- Mobile banking apps support many devices and OS versions.
- Code changes require extensive regression testing.
- Teams do not know which tests can be safely skipped for low-risk changes.

## 3. Operational Pain
- Long regression feedback loops.
- High compute cost.
- Developer frustration and delayed deployments.

## 4. Existing Workflow
- Baseline: CODE CHANGE → RUN FULL REGRESSION SUITE
- No optimization; tests unrelated to the change are run unnecessarily.

## 5. Proposed Solution
- TestSphere.AI Workflow: CODE CHANGE → IMPACT ANALYSIS → SELECT TESTS → RUN REQUIRED TESTS.
- Safe, optimized, and transparent test selection.

## 6. Architecture
- Modular backend (FastAPI), premium HTML/JS frontend.
- Engines: Change Analyzer, Dependency Analyzer, Coverage Analyzer, Risk Scorer.
- In-memory data processing with SQLite persistence.

## 7. Dataset
- Synthetic, realistic banking app data: Code Changes, Dependency Map, Test Coverage, Failure History, Device Matrix.

## 8. Change-impact Pipeline
- Identifies changed file → Checks direct dependencies → Checks transitive dependencies → Maps to test coverage → Evaluates risk.

## 9. Dependency Graph
- Traceable linkages between files (e.g., `payment.py` → `token_manager.py`).

## 10. Test Selection
- Risk score calculation (0 to 100).
- If score >= RUN_THRESHOLD or module is security-critical, select RUN. Otherwise, SKIP.

## 11. Transparent Rationale
- Every decision has a clear explanation (e.g., "Test indirectly depends on payment.py").
- No "black-box" decision making.

## 12. Baseline vs TestSphere.AI
- Compares Full Suite Execution against Smart Selection metrics.
- Experiment Lab simulates the exact time saved.

## 13. Runtime Reduction
- Significant time saved, proven by measurable experiment results.

## 14. Zero Affected-Test Misses
- Target: FALSE NEGATIVES = 0.
- Safety prioritized over maximum reduction.

## 15. Failure Cases
- Validated handling of missing data, empty DB, missing dependencies, and malformed CSVs without crashing.

## 16. Security
- Role-based token validation.
- Input validation (preventing path traversal).
- Secure overrides for critical modules.

## 17. Legacy Coexistence
- Both Legacy (Full Suite) and Smart Selector strategies available and switchable.

## 18. Rollback
- Demonstrated ability to revert strategies via an audited rollback endpoint.

## 19. User Validation
- Validation protocol established with key usability/trust questions for stakeholders.

## 20. Conclusion
- TestSphere.AI safely optimizes regression pipelines.
- Transparent, reliable, and demonstrably effective for mobile banking applications.
