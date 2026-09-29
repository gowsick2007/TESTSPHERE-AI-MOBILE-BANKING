# TestSphere.AI — Phase 2 Baseline State Audit

**Document:** `docs/phase2_baseline.md`  
**Milestone:** Transition from Phase 1 (35%) to Phase 2 (70%)  
**Audit Timestamp:** 2026-09-29  
**Branch:** `main`  
**Commit:** `f97a4c09f68058f5faca351828e9f6493fbe1479`  

---

## 1. System Inventory & Baseline State

### 1.1 Source Control & Environment
- **Current Branch:** `main`
- **Current HEAD Commit:** `f97a4c0` (`Finalize TestSphere AI validation and security`)
- **Runtime Environment:** Python 3.13.2 (64-bit), FastAPI 0.139.2, SQLite 3 (WAL mode), Pytest 9.1.1, Pandas 3.0.3, NetworkX 3.6.1

### 1.2 API Structure
TestSphere.AI currently exposes two application entry points:
1. `backend/main.py` (Primary Uvicorn entry point mounted at port 8001):
   - Prefixes all operational routers under `/api`:
     - `/api/auth` (`auth_routes.py`): `/login`, `/logout`, `/me`
     - `/api/data` (`data_routes.py`): `/status`, `/upload/full`, `/upload/{dataset_type}`, `/demo`, `/{dataset_type}` (DELETE), `/{dataset_type}/download`, `/template/{dataset_type}`, `/{dataset_type}/preview`
     - `/api/change` (`change_routes.py`): `/analyze`, `/history`, `/register`
     - `/api/tests` (`test_routes.py`): `/selection`, `/run-smart`, `/run-baseline`, `/coverage`, `/failures`, `/{test_id}`, `""`
     - `/api/experiment` (`experiment_routes.py`): `/run`, `/scenarios`, `/run-scenarios`
     - `/api/strategy` (`rollback_routes.py`): `""` (GET), `/rollback` (POST), `/history` (GET)
     - `/api/audit` (`audit_routes.py`): `/logs`, `/feedback`, `/feedback/stats`
     - `/api/what-if` (`main.py`): What-if simulation
   - Static mounts:
     - `/frontend` -> `frontend/`
     - `/` -> `frontend/index.html`
     - `/pages/{page_name}` -> `frontend/pages/{page_name}`
2. `API/main.py` (Legacy entry point):
   - Contains legacy unauthenticated endpoints: `/analyze-change`, `/test-selection`, `/run-baseline`, `/run-smart`, `/experiment`, `/strategy/rollback`.
   - **Finding:** Needs alignment so no unauthenticated bypass exists anywhere in the codebase.

### 1.3 Database Schema (`Data/testsphere.db`)
SQLite database containing 13 tables:
- `users`: User authentication, bcrypt password hashes, RBAC roles (`ADMIN`, `QA_ENGINEER`, `VIEWER`). (3 rows)
- `test_coverage`: 1,000 synthetic test definitions across 15 banking modules and 8 devices.
- `dependency_map`: Directed file dependency edges (source_file -> depends_on). (94 rows)
- `failure_history`: Historical test failures with severity, date, module, device. (2,400 rows)
- `device_matrix`: Hardware profiles with failure rates and risk categories. (8 rows)
- `code_changes`: Recorded commit change submissions. (17 rows)
- `experiment_ground_truth`: Scenario ground-truth affected & failure mappings. (5,000 rows)
- `dataset_metadata`: Tracking record counts and sources. (373 rows)
- `audit_log`: System security and execution audit trails. (283 rows)
- `rollback_history`: Strategy switch timestamps, users, reasons. (96 rows)
- `feedback`: Stakeholder survey responses. (0 rows - marked DATA REQUIRED)
- `selection_results`: Selector run outputs.
- `strategy_config`: Active selection strategy mode. (3 rows)

### 1.4 Dataset Structure
- **Canonical Datasets:** Stored as CSV in `Dataset/synthetic_canonical/`:
  - `test_coverage.csv` (1000 rows)
  - `dependency_map.csv` (84 rows)
  - `failure_history.csv` (2400 rows)
  - `device_matrix.csv` (8 rows)
  - `code_changes.csv` (15 rows)
  - `experiment_ground_truth.csv` (5000 rows)
- **Generator:** `Data_Generation/generate_dataset.py` with deterministic seed `12345`.
- **Reproducibility Test:** SHA256 byte-for-byte identical output verified across independent runs.

### 1.5 Authentication & RBAC
- **Token Mechanism:** In-memory `SESSIONS` table populated upon `/api/auth/login`.
- **Token Extraction:** Supports `Authorization: Bearer <token>`, `X-Token`, query parameter `?token=<token>`, and cookie `session_token`.
- **Roles:**
  - `ADMIN`: Full administrative control, dataset uploads, deletions, change registration, strategy rollback.
  - `QA_ENGINEER`: Change analysis, test selection, running smart/baseline tests, failure scenarios, submitting feedback. Restricted from rollback.
  - `VIEWER`: Read-only access to coverage, failures, health, audit logs, strategy history. All mutating/execution endpoints return HTTP 403 Forbidden.

### 1.6 Decision Engine & Risk Scoring
- **Approach:** Additive risk scoring with `RUN_THRESHOLD = 50`.
- **Weights:**
  - Direct Coverage: +40
  - Dependency Relationship: +30
  - Security Sensitive Module: +30
  - Critical Banking Module: +25
  - Historical Failure: +20
  - Recent Failure (within 90 days): +15
  - High-Risk Device: +10
- **Safety Overrides:** 7 mandatory safety rules enforce RUN regardless of numerical score (unknown dependency, unknown coverage, security critical, critical banking module, no failure data, low confidence < 0.5, rationale requirement).
- **Explainability:** `rationale_generator.py` produces human-readable bulleted evidence per test.

### 1.7 Current Automated Tests
- Test files located in `Tests/`: 14 test modules.
- Current status: 102 passed, 0 failed, 73 deprecation warnings (mostly `datetime.utcnow()` and FastAPI lifespan event deprecations).

---

## 2. Explicit Review of the 9 Phase-1 Baseline Issues

| # | Baseline Issue | Status in Phase-1 Review | Verified Current State | Action Required for Phase 2 |
|---|---|---|---|---|
| 1 | **Pytest Reproducibility Problems** | Flaky ordering / test pollution | 102 tests pass, but fixtures need standardization in `conftest.py` with isolated temp DB and clean client state. | Create comprehensive `conftest.py` with isolated DB fixtures; ensure zero collection errors with `--cache-clear`. |
| 2 | **Import-time Live HTTP Requests** | External network dependencies | Verified: No live HTTP or external network requests during module imports. | Enforce mock / offline fixtures; add test assertion forbidding unmocked socket calls. |
| 3 | **401 vs 403 Inconsistencies** | Some routes returned 200/422 on missing auth | `test_security_misuse.py` checks 401 on unauthenticated and 403 on VIEWER/unauthorized roles. | Verify every single protected mutation/analysis endpoint uniformly enforces 401 for unauthenticated/invalid tokens and 403 for insufficient roles. |
| 4 | **Unauthenticated Analysis/Selection Endpoints** | Legacy duplicate endpoints in `API/main.py` lacked auth | `API/main.py` had unauthenticated `/analyze-change`, `/test-selection`, etc. | Secure legacy endpoints with `Depends(get_user_from_token)` and align with `backend/main.py`. |
| 5 | **Low Precision / Over-Selection** | High false positives (584-796) due to safety overrides | CHG001 Payment: 921 RUN / 79 SKIP (125 TP, 796 FP). Zero False Negatives maintained. | Implement false-positive analysis breakdown and controlled threshold sensitivity framework. |
| 6 | **Runtime-only Dataset Generation** | Lack of static canonical dataset files | Canonical CSV files exist in `Dataset/synthetic_canonical/` with deterministic seed `12345`. | Maintain deterministic generation pipeline and document SHA256 hashes. |
| 7 | **Invalid JSON / Control-character Issue** | Potential corruption with newlines/quotes in rationales | Tested in `test_selection_json.py` with special characters. | Standardize Pydantic response models across all endpoints to guarantee RFC-8259 compliance. |
| 8 | **Benchmark / Documentation Mismatch** | Static claims contradicting empirical code output | Review 1 report documented actual numbers (5.7% time reduction for payment). | Dynamically calculate all benchmark metrics directly from runtime runs; never hardcode. |
| 9 | **Simulated vs Real Timing Confusion** | Reviewers conflating simulated test duration with CI runtime | Documented in Review 1 report, but needs explicit labelling in UI and API responses. | Add explicit `execution_type: "SIMULATED"` metadata to all benchmark and execution responses. |

---

## 3. Phase 2 Target Architecture Roadmap (70% Milestone)

1. **Test Infrastructure & Isolation:**
   - Unified `Tests/conftest.py` with standard fixtures (`api_client`, `admin_client`, `qa_client`, `viewer_client`, `unauth_client`, `clean_db`).
   - Clean verification: `python -m pytest --cache-clear Tests/ -v` produces zero collection errors and 0 unexpected failures.
2. **Security & API Matrix:**
   - Complete endpoint protection audit (`docs/api_security_matrix.md`).
   - Strict 401 vs 403 semantics across all routes.
3. **Engine Hardening:**
   - Cyclic dependency detection and bounded graph traversal.
   - Controlled threshold evaluation framework (thresholds 30, 40, 50, 60, 70).
   - Traceable safety overrides and granular signal breakdown.
4. **Execution Management Workflow:**
   - Implementation of execution planning and result tracking (`SIMULATED` vs `ACTUAL`).
5. **Strategy Versioning & Auditability:**
   - Strategy configuration versioning with audit preservation.
   - Transactional rollback with complete rollback-on-error guarantees.
6. **Analytics & Validation:**
   - Dedicated False-Negative and False-Positive analysis modules.
   - Stakeholder feedback submission and reporting pipeline.
   - Unified documentation and secret-scanning verification.
