# TestSphere.AI

## 1. Project Overview
TestSphere.AI is an intelligent, rule-based test selection engine. It reduces regression suite execution time by calculating the exact impact radius of any code change through deep dependency traversing, historic failure analysis, and safety-centric risk scoring. 

## 2. Problem Statement
Running a complete mobile banking regression suite on hundreds of devices for every single micro-change takes hours. TestSphere.AI resolves this by guaranteeing that only affected tests are selected for execution while maintaining a zero false-negative safety mandate.

## 3. Phase 1 Scope
Phase 1 (Core Engine & Application) encompasses universal dataset ingestion, dependency graph algorithms (BFS/DFS depth traversals), historical failure heuristics, risk-scoring matrix, and a deterministic Test Selection engine (RUN/SKIP) with human-readable rationale logic.

## 4. Architecture
- **Backend**: Python (FastAPI), heavily leveraging `pandas` and `networkx`.
- **Database**: In-memory optimized SQLite (`testsphere.db`).
- **Frontend**: Lightweight HTML/CSS/Vanilla JS (No heavy web frameworks) via dynamic REST bindings.

## 5. Installation & Configuration
Ensure you have Python 3.9+ installed.
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration Setup
The application requires a local `config.json` configuration file to run. To create it from the template:
```bash
cp config.example.json config.json  # On Windows PowerShell / Command Prompt: copy config.example.json config.json
```
Edit `config.json` locally to configure your local credentials and settings. Note that `config.json` is git-ignored to prevent sensitive local credentials from being committed to source control.


## 6. Running Backend
The backend initializes the database and serves API endpoints dynamically.
```bash
python backend/main.py
```
*Note: The frontend static files are served natively through the FastAPI instance on port 8001.*

## 7. Running Frontend
Navigate to `http://localhost:8001/` in any modern web browser after starting the backend.

## 8. Dataset Generation
The project relies on a strictly structured dataset matching Mobile Banking schema norms. Generate 1000+ realistic rows of test data via:
```bash
python Data_Generation/generate_dataset.py
```
*(You can also use the `Load Demo Dataset` button in the Web UI Data Management tab).*

## 9. Database Setup
The SQLite database automatically provisions itself at `Data/testsphere.db` on backend initialization. Manual schemas are defined in `Engine/database.py`.

## 10. Test Execution
Run the programmatic safety and CSV validation unit tests natively:
```bash
python run_tests_manually.py
```

## 11. Phase 1 Demo Flow
1. Load up `http://localhost:8001/` and Login.
2. Under **Data Management**, initialize the environment with the synthetic Demo Dataset.
3. Under **Change Analysis**, register an example file modification (e.g. `payment/payment.py`).
4. Under **Test Selector**, review the targeted test execution pipeline and verify the `RUN/SKIP` rationales.

## 12. Experiment Execution & Verified Performance
To programmatically prove the Time Reduction metrics and Zero False Negative guarantee, review the Jupyter Notebook:
`experiments/testsphere_experiment.ipynb`

### Verified Phase 1 Benchmark Results
- **Audit Verdict:** `PHASE 1 — PASS WITH DOCUMENTED LIMITATIONS`
- **Measured Runtime Reduction:** **5.1% – 9.1%** across single-module changes under strict security safety overrides.
- **Benchmark Example (Payment Module Change):**
  - **Baseline Suite:** 1,000 executed, 0 skipped, 2,238.33 seconds (~37.31 min).
  - **Smart Selection:** 921 executed, 79 skipped, 2,110.50 seconds (~35.18 min).
  - **Time Saved:** 127.83 seconds (**5.7% reduction**).
- **Safety Guarantee:** **0 False Negatives** across all verified change scenarios.

## 13. Known Limitations
- **Simulated Execution Benchmark:** Runtime reduction metrics are calculated using simulated test execution time metadata.
- **Transitive Dependency Depth:** Graph traversal is bounded at depth 3 for performance optimization.
- **Browser Automation:** Playwright browser automation was marked `NOT VERIFIED — ENVIRONMENT BLOCKED` due to Playwright driver CDN setup availability.
- **Stakeholder Validation:** Live user/stakeholder feedback is marked `DATA REQUIRED` (survey infrastructure is present in `feedback` table, pending live survey responses).

