# TestSphere.AI — Complete API Security & Protection Matrix

**Document:** `docs/api_security_matrix.md`  
**Generated:** Automated introspection of FastAPI routes (`backend/main.py`)  
**Platform:** TestSphere.AI Mobile Banking Change Impact Test Selector  
**Coverage:** 100% of REST and UI Endpoints Audited  

---

## 1. Authentication & RBAC Policy Overview

- **Public Routes:** Accessible without authentication headers or session tokens. Return `200 OK`.
- **Protected Routes:** Require valid authentication token via:
  - `Authorization: Bearer <token>`
  - `X-Token: <token>`
  - Cookie `session_token=<token>`
  - Query parameter `?token=<token>`
- **Authentication Semantics:**
  - **Missing Token:** Returns HTTP `401 Unauthorized` (`{"detail": "Unauthorized access. Invalid or missing token."}`)
  - **Invalid/Malformed Token:** Returns HTTP `401 Unauthorized`
  - **Valid Token + Insufficient Permission:** Returns HTTP `403 Forbidden` (`{"detail": "Permission Denied: ..."}`)
  - **Valid Token + Authorized Role:** Returns HTTP `200 OK` (or `201`/`204` as appropriate)
- **Role Permissions (RBAC):**
  - **`ADMIN`:** Full administrative access (data upload, table reset, change registration, emergency strategy rollback, test execution).
  - **`QA_ENGINEER`:** Change analysis, test selection, smart/baseline execution, experiment benchmarks, failure mode simulations, feedback submission. Strictly blocked (`403 Forbidden`) from strategy rollback.
  - **`VIEWER`:** Read-only access (coverage stats, failure history, health, audit logs, strategy history, what-if simulations). Strictly blocked (`403 Forbidden`) from all mutations and test executions.

---

## 2. Complete API Route Protection Matrix

| Method | Endpoint Path | Access Level | Required Role | Request Schema | Response Schema | Expected 401 | Expected 403 | Database Interaction | Audit Requirement |
|---|---|---|---|---|---|---|---|---|---|
| `GET` | `/health` | **Public** | None | None | `{"status": "ok"}` | No | No | None | No |
| `GET` | `/data-health` | **Public** | None | None | Data health metrics | No | No | `dataset_metadata` (READ) | No |
| `GET` | `/audit-log` | **Public** | None | None | Audit log list | No | No | `audit_log` (READ) | No |
| `GET` | `/` | **Public** | None | None | HTML (`index.html`) | No | No | None | No |
| `GET` | `/pages/{page_name}` | **Public** | None | None | HTML page template | No | No | None | No |
| `POST` | `/api/auth/login` | **Public** | None | `LoginRequest` | `LoginResponse` | No | No | `users` (SELECT) | Yes (`LOGIN`) |
| `POST` | `/api/auth/logout` | **Public** | None | None | `{"success": true}` | No | No | In-memory session delete | No |
| `GET` | `/api/auth/me` | **Public** | None | None | User profile or Guest | No | No | None | No |
| `GET` | `/api/health` | **Public** | None | None | `{"status": "ok"}` | No | No | None | No |
| `GET` | `/api/data-health` | **Public** | None | None | Data health metrics | No | No | `dataset_metadata` (READ) | No |
| `GET` | `/api/audit-log` | **Public** | None | None | Audit log list | No | No | `audit_log` (READ) | No |
| `GET` | `/api/data/status` | **Public** | None | None | Health + Metadata | No | No | `dataset_metadata` (READ) | No |
| `GET` | `/api/data/template/{dataset_type}` | **Public** | None | None | CSV Template stream | No | No | None | No |
| `GET` | `/api/data/{dataset_type}/download` | **Public** | None | None | CSV Content stream | No | No | Target table (READ) | No |
| `GET` | `/api/data/{dataset_type}/preview` | **Public** | None | None | JSON records (limit 50) | No | No | Target table (READ) | No |
| `POST` | `/api/data/upload/full` | **Protected** | `ADMIN`, `QA_ENGINEER` | Multipart CSV File | Validation Report | **401** | **403** (VIEWER) | `test_coverage`, `dependency_map`, etc. (WRITE) | Yes (`IMPORT_DATA`) |
| `POST` | `/api/data/upload/{dataset_type}` | **Protected** | `ADMIN`, `QA_ENGINEER` | Multipart CSV File | Import Result | **401** | **403** (VIEWER) | Target table (WRITE) | Yes (`IMPORT_DATA`) |
| `POST` | `/api/data/demo` | **Protected** | `ADMIN`, `QA_ENGINEER` | None | Demo generation summary | **401** | **403** (VIEWER) | All 6 datasets (RELOAD) | Yes (`LOAD_DEMO`) |
| `DELETE` | `/api/data/{dataset_type}` | **Protected** | `ADMIN`, `QA_ENGINEER` | None | `{"records_deleted": N}`| **401** | **403** (VIEWER) | Target table (DELETE) | Yes (`CLEAR_DATASET`) |
| `POST` | `/api/change/analyze` | **Protected** | `ADMIN`, `QA_ENGINEER`, `VIEWER` | `ChangeAnalysisRequest`| Impact analysis context | **401** | No | `dependency_map`, `test_coverage` (READ) | Yes (`CHANGE_ANALYSIS`) |
| `GET` | `/api/change/history` | **Public** | None | None | `{"changes": [...]}` | No | No | `code_changes` (READ) | No |
| `POST` | `/api/change/register` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ChangeAnalysisRequest`| `{"change_id": "CHG-..."}`| **401** | **403** (VIEWER) | `code_changes` (INSERT) | Yes (`REGISTER_CHANGE`) |
| `POST` | `/api/tests/selection` | **Protected** | `ADMIN`, `QA_ENGINEER`, `VIEWER` | `ChangeAnalysisRequest`| `SelectionResponse` | **401** | No | `test_coverage`, `dependency_map`, `failure_history` (READ) | Yes (`TEST_SELECTION`) |
| `POST` | `/api/tests/run-smart` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ChangeAnalysisRequest`| Smart execution results | **401** | **403** (VIEWER) | `test_coverage`, `failure_history` (READ) | Yes (`RUN_SMART_SUITE`) |
| `POST` | `/api/tests/run-baseline` | **Protected** | `ADMIN`, `QA_ENGINEER` | None | Baseline run results | **401** | **403** (VIEWER) | `test_coverage` (READ) | Yes (`RUN_BASELINE_SUITE`) |
| `GET` | `/api/tests/coverage` | **Public** | None | None | Module coverage stats | No | No | `test_coverage` (READ) | No |
| `GET` | `/api/tests/failures` | **Public** | None | None | Historical failure stats | No | No | `failure_history` (READ) | No |
| `GET` | `/api/tests/{test_id}` | **Public** | None | None | Single test metadata | No | No | `test_coverage` (READ) | No |
| `GET` | `/api/tests` | **Public** | None | None | All tests array | No | No | `test_coverage` (READ) | No |
| `POST` | `/api/experiment/run` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ChangeAnalysisRequest`| Side-by-side benchmark | **401** | **403** (VIEWER) | All datasets (READ) | Yes (`RUN_EXPERIMENT`) |
| `GET` | `/api/experiment/scenarios` | **Public** | None | None | Scenario definitions | No | No | None | No |
| `POST` | `/api/experiment/run-scenarios` | **Protected** | `ADMIN`, `QA_ENGINEER` | None | 5 safety assertion results | **401** | **403** (VIEWER) | All datasets (READ) | Yes (`RUN_FAILURE_SCENARIOS`) |
| `GET` | `/api/strategy` | **Public** | None | None | Current strategy state | No | No | `strategy_config` (READ) | No |
| `POST` | `/api/strategy/rollback` | **Protected** | **`ADMIN` ONLY** | `RollbackRequest` | Rollback status | **401** | **403** (QA, VIEWER) | `strategy_config` (UPDATE), `rollback_history` (INSERT) | Yes (`ROLLBACK`) |
| `GET` | `/api/strategy/history` | **Public** | None | None | Rollback audit entries | No | No | `rollback_history` (READ) | No |
| `GET` | `/api/audit/logs` | **Public** | None | None | System audit trail | No | No | `audit_log` (READ) | No |
| `POST` | `/api/audit/feedback` | **Protected** | `ADMIN`, `QA_ENGINEER`, `VIEWER` | `FeedbackRequest` | `{"success": true}` | **401** | No | `feedback` (INSERT) | Yes (`SUBMIT_FEEDBACK`) |
| `GET` | `/api/strategy/versions` | **Public** | None | None | Version history list | No | No | `strategy_versions` (READ) | No |
| `POST` | `/api/strategy/versions` | **Protected** | **`ADMIN` ONLY** | `StrategyVersionCreateRequest` | Created version | **401** | **403** (QA, VIEWER) | `strategy_versions` (INSERT) | Yes (`CREATE_STRATEGY_VERSION`) |
| `POST` | `/api/execution/plan` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ExecutionPlanCreateRequest` | Created plan details | **401** | **403** (VIEWER) | `execution_plans` (INSERT) | Yes (`CREATE_EXECUTION_PLAN`) |
| `POST` | `/api/execution/run` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ExecutionRunRequest` | Plan execution run output | **401** | **403** (VIEWER) | `execution_plans` (UPDATE), `execution_results` (INSERT) | Yes (`RUN_EXECUTION_PLAN`) |
| `GET` | `/api/execution/plan/{plan_id}` | **Public** | None | None | Plan details & results | No | No | `execution_plans`, `execution_results` (READ) | No |
| `GET` | `/api/execution/history` | **Public** | None | None | Historical plan records | No | No | `execution_plans` (READ) | No |
| `POST` | `/api/experiment/create` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ExperimentCreateRequest` | Stored experiment record | **401** | **403** (VIEWER) | `experiments` (INSERT) | Yes (`CREATE_EXPERIMENT`) |
| `GET` | `/api/experiment/history` | **Public** | None | None | Stored experiments list | No | No | `experiments` (READ) | No |
| `GET` | `/api/experiment/{experiment_id}` | **Public** | None | None | Single experiment record | No | No | `experiments` (READ) | No |
| `PUT` | `/api/experiment/{experiment_id}` | **Protected** | `ADMIN`, `QA_ENGINEER` | Any update payload | `400 Bad Request` (Immutability Lock) | **401** | **403** (VIEWER) | None (Rejected) | Yes (`UPDATE_EXPERIMENT_ATTEMPT`) |
| `POST` | `/api/experiment/compare` | **Protected** | `ADMIN`, `QA_ENGINEER` | `ExperimentCompareRequest` | Metric deltas & comparison | **401** | **403** (VIEWER) | `experiments` (READ) | Yes (`COMPARE_EXPERIMENTS`) |
| `GET` | `/api/experiment/threshold-evaluation` | **Public** | None | None | Controlled threshold metrics | No | No | `failure_scenarios` (READ) | No |
| `GET` | `/api/analytics/summary` | **Public** | None | None | Comprehensive analytics KPIs | No | No | All system tables (READ) | No |
| `GET` | `/api/analytics/false-negatives` | **Public** | None | None | False negative diagnostic audits | No | No | `failure_scenarios` (READ) | No |
| `GET` | `/api/analytics/false-positives` | **Public** | None | None | Over-selection diagnostic audits | No | No | `test_coverage` (READ) | No |
| `GET` | `/api/analytics/threshold-sensitivity` | **Public** | None | None | Threshold curve metrics | No | No | Multi-threshold evaluation | No |
| `GET` | `/api/audit/feedback/list` | **Public** | None | None | Full feedback logs | No | No | `feedback` (READ) | No |

---

## 3. Negative Misuse & Security Verification Suite

Every protected route in the matrix is verified via automated integration tests in:
- `Tests/test_security_misuse.py` (Unauthenticated 401 & VIEWER 403 enforcement)
- `Tests/test_security_new.py` (ADMIN vs QA_ENGINEER vs VIEWER authorization)
- `Tests/test_api.py` (Standard API integration verification)

**Verification Command:**
```bash
python -m pytest Tests/test_security_misuse.py Tests/test_security_new.py Tests/test_api.py -v
```