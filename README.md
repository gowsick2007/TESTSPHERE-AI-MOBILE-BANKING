# TestSphere.AI

## 1. Project Overview
TestSphere.AI is an intelligent, rule-based test selection engine. It reduces regression suite execution time by calculating the exact impact radius of any code change through deep dependency traversing, historic failure analysis, and safety-centric risk scoring. 

## 2. Problem Statement
Running a complete mobile banking regression suite on hundreds of devices for every single micro-change takes hours. TestSphere.AI resolves this by prioritizing safety and minimizing missed affected tests through conservative risk scoring.

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
To programmatically evaluate Time Reduction metrics and safety performance, review the Jupyter Notebook:
`experiments/testsphere_experiment.ipynb`

### Verified Phase 1 Benchmark Results (Seed 12345, Threshold 50)
- **Scoring Strategy:** `RUN_THRESHOLD = 50` (Retained). The scoring strategy prioritizes safety and minimizing missed affected tests over aggressive test-suite reduction. This can result in a higher number of false-positive RUN decisions.
- **Overall Aggregate Results (5 Scenarios, 5,000 Decisions):**
  - **True Positives (TP):** 621
  - **True Negatives (TN):** 469
  - **False Positives (FP):** 3,909
  - **False Negatives (FN):** 1 (Recall: **99.84%**)
  - **Overall Precision:** **13.71%** (0.1371)
  - **Overall Recall:** **99.84%** (0.9984)
  - **Total RUN Decisions:** 4,530
  - **Total SKIP Decisions:** 470
- **Scenario Breakdown (SIMULATED EXECUTION TIME):**
  - **CHG001 (Payment):** RUN=991, SKIP=9 | TP=130, TN=9, FP=861, FN=0 | Prec=0.1312, Rec=1.0000 | SIMULATED EXECUTION TIME: 37.49 min vs 37.80 min (0.8% reduction)
  - **CHG003 (Authentication):** RUN=730, SKIP=270 | TP=68, TN=270, FP=662, FN=0 | Prec=0.0932, Rec=1.0000 | SIMULATED EXECUTION TIME: 30.53 min vs 37.80 min (19.2% reduction)
  - **CHG008 (Transaction):** RUN=959, SKIP=41 | TP=142, TN=41, FP=817, FN=0 | Prec=0.1481, Rec=1.0000 | SIMULATED EXECUTION TIME: 36.51 min vs 37.80 min (3.4% reduction)
  - **CHG011 (Notification):** RUN=920, SKIP=80 | TP=82, TN=79, FP=838, FN=1 | Prec=0.0891, Rec=0.9880 | SIMULATED EXECUTION TIME: 35.42 min vs 37.80 min (6.3% reduction)
  - **CHG_MULTI (Payment + Auth):** RUN=930, SKIP=70 | TP=199, TN=70, FP=731, FN=0 | Prec=0.2140, Rec=1.0000 | SIMULATED EXECUTION TIME: 35.84 min vs 37.80 min (5.2% reduction)

## 13. Known Limitations
- **SIMULATED EXECUTION TIME:** Runtime reduction metrics are calculated using simulated test execution time metadata, not real hardware or production execution time.
- **Transitive Dependency Depth:** Graph traversal is bounded at depth 3 for performance optimization.
- **Browser Automation:** Playwright browser automation was marked `NOT VERIFIED — ENVIRONMENT BLOCKED` due to environment driver setup.
- **Stakeholder Validation:** Live user/stakeholder feedback is marked `DATA REQUIRED` (survey infrastructure is present in `feedback` table, pending live survey responses).


