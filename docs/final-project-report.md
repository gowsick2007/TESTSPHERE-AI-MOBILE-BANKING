# TestSphere.AI
## Change-Impact Test Selector for Mobile Banking

### 1. Problem Statement
A mobile banking application is released on many device types, requiring extensive regression testing. Development teams struggle to determine which tests can be safely skipped when a code change is low-risk. The solution must identify affected tests, safely skip unaffected ones, provide transparent explanation, and guarantee zero false negatives (no missed affected tests), all while reducing regression execution time.

### 2. Operational Pain
Running the full regression suite on every single code change is time-consuming, expensive, and slows down the delivery pipeline. Developers wait hours for results of small changes, leading to reduced productivity and delayed deployments.

### 3. Existing/Legacy Workflow
The legacy workflow operates under a simple paradigm:
CODE CHANGE → RUN FULL REGRESSION SUITE
Every time a code change is made, regardless of its size, module, or impact, the entire suite is executed.

### 4. Proposed TestSphere.AI Workflow
The proposed workflow introduces an intelligent layer:
CODE CHANGE → IMPACT ANALYSIS → SELECT TESTS → RUN ONLY REQUIRED TESTS
This ensures fast feedback loops by skipping tests that are mathematically unlinked to the change.

### 5. Field Workflow Map
1. Developer creates code change
2. Change submitted
3. TestSphere.AI receives changed files
4. Dependency analysis (direct & transitive)
5. Coverage analysis
6. Failure history lookup
7. Risk assessment
8. Test selection
9. RUN / SKIP decision
10. Transparent rationale
11. Selected tests executed
12. Results recorded
13. Audit trail

### 6. System Architecture
The system uses a modular backend (FastAPI) and a frontend dashboard. The engine comprises several analyzers: Change Analyzer, Dependency Analyzer, Coverage Analyzer, Failure Analyzer, and a Risk Scorer, connected to a SQLite database.

### 7. Dataset Design
The dataset represents a realistic mobile banking app across 5 tables:
- `code_changes`: Information on modified files.
- `dependency_map`: Relationships between components.
- `test_coverage`: Tests mapped to modules and devices.
- `failure_history`: Historical test results.
- `device_matrix`: Devices and OS versions.

### 8. Universal Dataset Ingestion
TestSphere.AI provides universal CSV ingestion with auto-mapping for synonyms, missing value detection, schema validation, type casting (numeric/date), duplicate removal, and transparent repair strategies to handle real-world dirty data.

### 9. Change Impact Analysis
When a file is modified, its module is identified and the change type (e.g., MODIFIED, SECURITY_PATCH) and risk level are calculated to establish the blast radius.

### 10. Dependency Analysis
The system builds a dependency graph mapping direct and transitive dependencies up to a specific depth to ensure indirect impacts are not missed.

### 11. Coverage Analysis
Tests that directly cover the modified file or its dependent files are prioritized and flagged for selection.

### 12. Failure Intelligence
Historical failures are factored in. Tests with a history of failing frequently on certain devices or modules are assigned a higher risk score.

### 13. Test Selection
A risk score is computed using coverage, dependencies, failure history, device risk, and security sensitivity. If the score exceeds a predefined threshold, the test is selected.

### 14. Transparent RUN/SKIP Rationale
For every test, TestSphere.AI generates a clear rationale string explaining why it was run or skipped (e.g., "Test covers payment.py, which was directly modified").

### 15. Security & Misuse Resistance
The API is protected with token-based authentication. Inputs are validated for path traversals. CSV uploads are verified to avoid SQL injection, and security overrides ensure that critical components never bypass tests.

### 16. Baseline
The baseline execution runs the full regression suite for a change, serving as the benchmark for time reduction and completeness.

### 17. Experimental Method
An experimental lab is used to compare the Baseline vs TestSphere.AI by simulating multi-file and single-file changes and calculating execution time and selection accuracy.

### 18. Experimental Results
Experiments confirmed that the smart selector successfully reduces the tests run without compromising safety.
(Data derived from `testsphere_experiment.ipynb`)

### 19. Runtime Reduction
Runtime was significantly reduced. Across standard test runs, test execution time dropped by ~30% to ~70% depending on the change scope.

### 20. Affected-Test Safety
Zero False Negatives. The system prioritizes safety over maximum reduction. No tests that were actually affected (based on dependency and coverage mapping) were skipped.

### 21. Error Analysis
False positives occasionally happen due to conservative fallback strategies or transitive dependencies being weakly coupled. However, false negatives remain zero, meaning it successfully avoids missing a critical test.

### 22. Failure Cases
Handled failure cases include:
1. Missing required fields in dataset
2. Security-critical changes
3. Missing dependencies
4. Invalid authorization
5. Empty database

### 23. Legacy Coexistence
The system can toggle between `SMART_SELECTION` and `LEGACY_FULL_SUITE`, allowing developers to keep the old workflow available at any time.

### 24. Rollback Demonstration
The rollback endpoint allows administrators to instantly revert to the legacy full-suite strategy if the smart selector produces uncertain results, logging the rollback in the audit trail.

### 25. What-If Analysis
A what-if tool allows users to query hypothetical scenarios ("What happens if I change X on device Y?"), providing estimated runtimes and risk assessments instantly without executing the suite.

### 26. Experiment Lab
The built-in Experiment Lab operates in isolation, ensuring production data is untainted while allowing stakeholders to run simulations and verify time savings.

### 27. User/Stakeholder Validation
Validation protocol prepared; real participant responses required. 
Feedback form addresses:
1. Is the RUN/SKIP decision understandable?
2. Is the rationale clear?
3. Would you trust the system for low-risk changes?
4. Is the interface easy to use?

### 28. Limitations
- Unmapped transitive dependencies can lead to broader-than-necessary test execution.
- Relies heavily on the accuracy of the underlying test coverage and dependency mapping datasets.

### 29. Why This Approach Is Appropriate
Unlike opaque ML models, the rule-based approach provides absolute transparency, determinism, and safety, which are critical in the heavily regulated mobile banking sector.

### 30. Conclusion
TestSphere.AI successfully solves the operational pain of bloated regression suites. By integrating transparent dependency tracing and failure intelligence, it demonstrably reduces test execution time while maintaining a zero false-negative safety guarantee.
