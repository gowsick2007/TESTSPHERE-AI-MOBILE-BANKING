import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def create_report():
    doc = Document()

    # Page setup - Margins 1 inch
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Styling colors
    PRIMARY_COLOR = RGBColor(27, 54, 93)     # Deep Navy (#1B365D)
    SECONDARY_COLOR = RGBColor(0, 128, 128)  # Teal (#008080)
    DARK_TEXT = RGBColor(40, 40, 40)

    # Base Normal Style
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = DARK_TEXT
    normal_style.paragraph_format.line_spacing = 1.15
    normal_style.paragraph_format.space_after = Pt(6)

    def set_cell_background(cell, fill_color):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_color}"/>')
        tcPr.append(shd)

    def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
        tcPr.append(tcMar)

    def add_title(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(20)
        p.paragraph_format.space_after = Pt(6)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(22)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR

    def add_subtitle(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(20)
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(13)
        run.font.color.rgb = SECONDARY_COLOR

    def add_h1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(16)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(13)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR

    def add_callout(text, title="NOTE"):
        tbl = doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = tbl.cell(0, 0)
        set_cell_background(cell, "F0F4F8")
        set_cell_margins(cell, top=120, bottom=120, left=180, right=180)
        
        tcPr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(f'<w:tcBorders {nsdecls("w")}><w:left w:val="single" w:sz="24" w:space="0" w:color="1B365D"/><w:top w:val="none"/><w:right w:val="none"/><w:bottom w:val="none"/></w:tcBorders>')
        tcPr.append(borders)

        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r_t = p.add_run(f"[{title}] ")
        r_t.bold = True
        r_t.font.color.rgb = PRIMARY_COLOR
        r_b = p.add_run(text)
        r_b.font.size = Pt(10.5)
        
        p_space = doc.add_paragraph()
        p_space.paragraph_format.space_before = Pt(0)
        p_space.paragraph_format.space_after = Pt(4)

    # ---------------------------------------------------------
    # HEADER / METADATA
    # ---------------------------------------------------------
    add_title("TestSphere.AI – Change Impact Test Selector\nfor Mobile Banking Applications")
    add_subtitle("C28 Semester 5 Project — Review 1 Report (35% Completion Milestone)")

    meta_table = doc.add_table(rows=5, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Course & Academic Phase", "C28 Semester 5 Project — Review 1 (2025–2026)"),
        ("Project Completion Milestone", "35% Completed"),
        ("GitHub Repository", "https://github.com/gowsick2007/TESTSPHERE-AI-MOBILE-BANKING"),
        ("Core Stack", "FastAPI (Python), SQLite3, HTML5/CSS3/JS, Pytest"),
        ("Primary Project Domain", "Data Science / Intelligent Software Test Selection")
    ]
    for idx, (k, v) in enumerate(meta_data):
        r = meta_table.rows[idx]
        r.cells[0].text = k
        r.cells[0].paragraphs[0].runs[0].font.bold = True
        r.cells[0].paragraphs[0].runs[0].font.color.rgb = PRIMARY_COLOR
        r.cells[1].text = v
        set_cell_background(r.cells[0], "F4F6F9")
        set_cell_background(r.cells[1], "FFFFFF")
        set_cell_margins(r.cells[0], top=80, bottom=80, left=100, right=100)
        set_cell_margins(r.cells[1], top=80, bottom=80, left=100, right=100)

    doc.add_page_break()

    # ---------------------------------------------------------
    # ABSTRACT
    # ---------------------------------------------------------
    add_h1("Abstract")
    doc.add_paragraph(
        "Mobile banking applications require frequent software updates for security patches, feature enhancements, and bug fixes across functional modules like Payment, Authentication, Transaction Processing, and Notifications. Running a full regression suite after every small code edit introduces significant pipeline latency. This project report presents the Review 1 (35% completion) status of TestSphere.AI, a data-driven change-impact test selection system for mobile banking software."
    )
    doc.add_paragraph(
        "TestSphere.AI analyzes code change metadata, file dependency graphs, test coverage maps, historical test failure logs, and mobile hardware risk levels to classify automated tests into RUN and SKIP decisions. The selector relies on an additive risk-scoring formula combined with seven mandatory safety overrides that prioritize test safety over aggressive skipping. Ground truth data was synthetically generated using controlled scenario rules and seeded/randomized associations for prototype evaluation. In baseline benchmarking against a 1,000-test synthetic regression suite (full execution time of 2,238.33 seconds / ~37.3 minutes), TestSphere.AI demonstrated execution time reductions ranging from 5.1% to 23.4%. TestSphere.AI achieved 100% recall in four of the five evaluated scenarios. The notification scenario achieved 82.3% recall, with 29 affected tests not selected. This report details the system architecture, dataset design, scoring logic, security controls, strategy rollback, and initial experimental evaluation."
    )

    # ---------------------------------------------------------
    # 1. INTRODUCTION
    # ---------------------------------------------------------
    add_h1("1. Introduction")
    doc.add_paragraph(
        "Continuous integration and continuous delivery (CI/CD) pipelines rely heavily on automated regression testing to prevent software defects from reaching production environments. In mobile banking software, quality assurance is critical because application bugs can lead to security vulnerabilities, transaction failures, compliance breaches, and user dissatisfaction."
    )
    doc.add_paragraph(
        "As mobile banking projects expand, QA teams accumulate large suites of automated test scripts to cover various user journeys, API endpoints, and mobile device configurations. However, running a complete 1,000-test suite for small code changes (such as fixing a typo in a login validation label or tweaking a notification text color) consumes unnecessary time and hardware resources. TestSphere.AI addresses this bottleneck by evaluating code changes and selecting only the tests that are likely to be affected, while maintaining safety rules to protect critical banking functions."
    )

    # ---------------------------------------------------------
    # 2. PROBLEM STATEMENT
    # ---------------------------------------------------------
    add_h1("2. Problem Statement")
    doc.add_paragraph(
        "Mobile banking CI/CD pipelines face two opposing challenges:"
    )
    doc.add_paragraph("1. Pipeline Latency: Running full regression suites after every minor commit causes feedback delays for developers, taking over 37 minutes per build in our benchmark.")
    doc.add_paragraph("2. Defect Risk: Skipping tests manually or randomly risks missing regression bugs in critical financial paths like payments or authentication.")
    doc.add_paragraph(
        "The main problem identified during early project planning was the lack of an automated, transparent mechanism to identify affected tests based on objective repository data. TestSphere.AI was developed to provide a data-driven test selection workflow that balances testing speed with safety."
    )

    # ---------------------------------------------------------
    # 3. PROJECT OBJECTIVES
    # ---------------------------------------------------------
    add_h1("3. Project Objectives")
    doc.add_paragraph("The primary technical goals for the Review 1 (35% completion) milestone were:")
    doc.add_paragraph("• Design a modular system architecture combining a FastAPI backend, SQLite database, and web frontend.")
    doc.add_paragraph("• Build a synthetic data generation pipeline to seed test coverage maps, file dependency graphs, device matrices, and failure logs.")
    doc.add_paragraph("• Implement an additive, rule-based risk-scoring engine (+40 coverage, +30 dependency, +30 security, +25 critical module, +20 historical failure, +15 recent failure, +10 high-risk device).")
    doc.add_paragraph("• Enforce seven mandatory safety overrides to force RUN decisions when data is missing or critical modules are involved.")
    doc.add_paragraph("• Implement Role-Based Access Control (RBAC), configuration isolation, audit logging, and strategy rollback capabilities.")
    doc.add_paragraph("• Evaluate selector performance across five controlled experiment scenarios using precision, recall, and runtime reduction metrics.")

    # ---------------------------------------------------------
    # 4. DATA SCIENCE APPROACH & PROJECT SCOPE
    # ---------------------------------------------------------
    add_h1("4. Data Science Approach & Scope")
    doc.add_paragraph(
        "TestSphere.AI is primarily a Data Science / Intelligent Test Selection project supported by standard web software engineering components. Rather than relying on black-box machine learning models at this stage, the data science approach centers on exploratory data analysis, graph dependency traversal, multi-factor risk weighting, and precision/recall performance evaluation."
    )
    doc.add_paragraph(
        "The current implementation processes structured datasets (coverage maps, dependency edges, historical execution logs) to calculate evidence-based risk scores for each test. Machine learning optimization is planned as a future enhancement for Phase 2, while the current Phase 1 foundation focuses on transparent data analytical reasoning."
    )

    # ---------------------------------------------------------
    # 5. EXISTING PRACTICE VS. PROPOSED SYSTEM
    # ---------------------------------------------------------
    add_h1("5. Existing Practice vs. Proposed System")
    
    comp_tbl = doc.add_table(rows=5, cols=3)
    comp_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["Dimension", "Existing Practice (Full Suite / Manual)", "Proposed System (TestSphere.AI)"]
    for i, h in enumerate(headers):
        cell = comp_tbl.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)

    rows_data = [
        ("Execution Strategy", "Executes 1000/1000 tests on every commit, or relies on manual unguided filtering.", "Analyzes commit changes and executes impacted tests while skipping unimpacted ones."),
        ("Pipeline Feedback Time", "Slow (approx. 37.3 minutes per build).", "Faster (approx. 28.6 to 35.2 minutes per build, reducing runtime by up to 23.4%)."),
        ("Decision Safety", "No explicit safety checks; manual skips risk missing critical tests.", "Enforces 7 mandatory safety overrides (forced RUN for security, critical modules, missing data)."),
        ("Audit & Control", "No audit log or instant recovery mechanism.", "RBAC enforcement, central audit logging, and instant strategy rollback to full suite.")
    ]
    for r_idx, row in enumerate(rows_data, start=1):
        r_cells = comp_tbl.rows[r_idx].cells
        for c_idx, val in enumerate(row):
            r_cells[c_idx].text = val
            set_cell_background(r_cells[c_idx], "F4F6F9" if r_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(r_cells[c_idx], top=80, bottom=80, left=100, right=100)

    doc.add_paragraph()

    # ---------------------------------------------------------
    # 6. SYSTEM ARCHITECTURE & MODULES
    # ---------------------------------------------------------
    add_h1("6. System Architecture & Core Modules")
    doc.add_paragraph(
        "TestSphere.AI uses a tiered architecture where the web frontend interacts with FastAPI REST endpoints, which delegate business logic to core engine modules and the Data Access Layer (DAL)."
    )

    add_callout(
        "Frontend (HTML/CSS/JS UI) → FastAPI Backend (`backend/api/`) → Selection Engine (`Engine/test_selector.py`) → Data Access Layer (`Engine/data_access.py`) → SQLite Database (`Data/testsphere.db`)",
        title="ARCHITECTURE DATA FLOW"
    )

    doc.add_paragraph("Key Engine Components:")
    doc.add_paragraph("• `Engine/change_analyzer.py`: Parses changed file paths, identifies affected modules, and checks security sensitivity.")
    doc.add_paragraph("• `Engine/dependency_analyzer.py`: Traverses direct and transitive file dependency edges in `dependency_map`.")
    doc.add_paragraph("• `Engine/coverage_analyzer.py`: Maps impacted source files to test scripts in `test_coverage`.")
    doc.add_paragraph("• `Engine/failure_analyzer.py`: Checks test execution failure history over the last 90 days.")
    doc.add_paragraph("• `Engine/risk_scorer.py`: Computes additive risk scores for each test script.")
    doc.add_paragraph("• `Engine/safety_overrides.py`: Evaluates seven mandatory safety rules to force RUN decisions.")
    doc.add_paragraph("• `Engine/rationale_generator.py`: Generates human-readable explanations for selection decisions.")
    doc.add_paragraph("• `Rollback/rollback_manager.py`: Manages strategy state (`SMART_SELECTOR` vs `LEGACY_FULL_SUITE`) and records rollback events.")
    doc.add_paragraph("• `Security/auth.py`: Handles session authentication, password hashing, and role checks (ADMIN, QA_ENGINEER, VIEWER).")

    # ---------------------------------------------------------
    # 7. DATASET & DATA PREPARATION
    # ---------------------------------------------------------
    add_h1("7. Dataset & Data Preparation")
    doc.add_paragraph(
        "To enable controlled experimentation without requiring proprietary banking repository data, TestSphere.AI includes an automated dataset generation module (`Data_Generation/generate_dataset.py`). The generator populates the SQLite database with synthetic records for testing."
    )

    add_callout(
        "Synthetic Ground Truth Clarification: Ground truth records in `experiment_ground_truth` are synthetically generated using controlled scenario rules and seeded/randomized associations. They were created specifically for evaluating the prototype selection logic in controlled change scenarios and are NOT claimed to represent real production banking test history.",
        title="DATASET NATURE & GROUND TRUTH DEFINITION"
    )

    ds_tbl = doc.add_table(rows=12, cols=3)
    ds_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    ds_headers = ["Table Name", "Record Count / Nature", "Functional Purpose"]
    for i, h in enumerate(ds_headers):
        cell = ds_tbl.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)

    tables_info = [
        ("test_coverage", "1,000 rows", "Stores test script metadata, target file paths, modules, devices, and execution times."),
        ("dependency_map", "84 rows", "Defines directional source file dependency edges (source_file → depends_on)."),
        ("failure_history", "2,400 rows", "Contains historical test failure records over the past 90 days."),
        ("device_matrix", "8 rows", "Mobile device profiles with hardware risk levels (Pixel 8, iPhone 15, etc.)."),
        ("code_changes", "15 rows", "Recorded commit change entries with module classifications and risk tags."),
        ("experiment_ground_truth", "Scenario-generated mappings, with up to 5,000 mappings possible across the five controlled scenarios.", "Contains scenario-generated experiment ground truth mappings for change impact benchmarking."),
        ("selection_results", "Dynamic", "Stores engine test selection decisions and generated rationale strings."),
        ("strategy_config", "1 active row", "Active selection strategy state (SMART_SELECTOR vs LEGACY_FULL_SUITE)."),
        ("rollback_history", "Audit rows", "Audit records tracking strategy rollback events, users, timestamps, and reasons."),
        ("feedback", "0 rows (DATA REQUIRED)", "Survey schema (Q1-Q5 ratings) for collecting stakeholder feedback."),
        ("audit_log", "Audit rows", "System security log tracking user logins, file uploads, and strategy updates.")
    ]
    for r_idx, row in enumerate(tables_info, start=1):
        r_cells = ds_tbl.rows[r_idx].cells
        for c_idx, val in enumerate(row):
            r_cells[c_idx].text = val
            set_cell_background(r_cells[c_idx], "F4F6F9" if r_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(r_cells[c_idx], top=60, bottom=60, left=100, right=100)

    doc.add_paragraph()

    # ---------------------------------------------------------
    # 8. RISK SCORING AND SAFETY OVERRIDES
    # ---------------------------------------------------------
    add_h1("8. Risk Scoring & Safety Overrides")
    add_h2("8.1 Additive Risk Scoring Mechanics")
    doc.add_paragraph(
        "The risk scoring module (`Engine/risk_scorer.py`) calculates a numerical risk score for each test script by evaluating seven weighted factors:"
    )
    doc.add_paragraph("• Direct Coverage (+40 points): Test script directly targets a file modified in the commit.")
    doc.add_paragraph("• Dependency Path (+30 points): Test covers a file linked via the dependency graph.")
    doc.add_paragraph("• Security-Sensitive Change (+30 points): Commit involves security, authentication, or encryption code.")
    doc.add_paragraph("• Critical Banking Module (+25 points): Test belongs to Authentication, Payment, or OTP modules.")
    doc.add_paragraph("• Historical Failure (+20 points): Test module has recorded past failures in `failure_history`.")
    doc.add_paragraph("• Recent Failure (+15 points): Test script has failed within the last 90 days.")
    doc.add_paragraph("• High-Risk Device (+10 points): Test targets high-risk mobile hardware/OS profiles.")
    doc.add_paragraph("Decision Rule: RUN_THRESHOLD = 50. A test is marked for RUN when its calculated score is greater than or equal to 50. Otherwise, it is marked for SKIP.")

    add_h2("8.2 Mandatory Safety Overrides")
    doc.add_paragraph(
        "To ensure test safety takes precedence over speed, `Engine/safety_overrides.py` enforces seven explicit safety rules that force a RUN decision regardless of numeric score:"
    )
    doc.add_paragraph("1. Rule 1 (Unknown Dependency): Triggered when dependency graph data is missing. Forces RUN to avoid missing unmapped dependencies.")
    doc.add_paragraph("2. Rule 2 (Unknown Coverage): Triggered when test coverage data is unavailable. Forces RUN to ensure unmapped tests execute.")
    doc.add_paragraph("3. Rule 3 (Security Critical): Triggered when a test is marked `is_security_critical=1`. Forces RUN to protect security paths.")
    doc.add_paragraph("4. Rule 4 (Critical Banking Module): Triggered when changes touch Authentication, Payment, or OTP modules. Forces RUN for core financial logic.")
    doc.add_paragraph("5. Rule 5 (No Failure Data): Triggered when historical failure logs are absent. Forces RUN as a safe fallback.")
    doc.add_paragraph("6. Rule 6 (Low Confidence): Triggered when engine confidence falls below 0.5. Forces RUN under uncertainty.")
    doc.add_paragraph("7. Rule 7 (Rationale Requirement): Requires every test skip decision to generate a detailed explanation, preventing unexplained test drops.")

    # ---------------------------------------------------------
    # 9. EXPERIMENTAL RESULTS AND BENCHMARKING
    # ---------------------------------------------------------
    add_h1("9. Experimental Results & Benchmarking")
    doc.add_paragraph(
        "We evaluated TestSphere.AI across five controlled commit scenarios comparing Smart Selection against a Legacy Full Suite Baseline (1,000 tests, execution time 2,238.33 seconds / ~37.3 minutes)."
    )

    exp_tbl = doc.add_table(rows=6, cols=12)
    exp_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    exp_headers = ["Scenario", "Changed File", "Total", "Affected", "RUN", "SKIP", "TP", "TN", "FP", "FN", "Recall", "Time Red."]
    for i, h in enumerate(exp_headers):
        cell = exp_tbl.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=60, bottom=60, left=50, right=50)

    exp_data = [
        ("CHG001 Payment", "payment/payment.py", "1000", "125", "921", "79", "125", "79", "796", "0", "100.0%", "5.7%"),
        ("CHG003 Auth", "auth/login.py", "1000", "90", "674", "326", "90", "326", "584", "0", "100.0%", "23.4%"),
        ("CHG008 Transfer", "transaction/txn_limit.py", "1000", "96", "842", "158", "96", "158", "746", "0", "100.0%", "11.3%"),
        ("CHG011 Push Notif.", "notification/push.py", "1000", "164", "927", "73", "135", "44", "792", "29", "82.3%", "5.1%"),
        ("CHG_MULTI Multi-File", "payment.py + login.py", "1000", "181", "830", "170", "181", "170", "649", "0", "100.0%", "11.7%")
    ]
    for r_idx, row in enumerate(exp_data, start=1):
        r_cells = exp_tbl.rows[r_idx].cells
        for c_idx, val in enumerate(row):
            r_cells[c_idx].text = val
            set_cell_background(r_cells[c_idx], "F4F6F9" if r_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(r_cells[c_idx], top=60, bottom=60, left=50, right=50)

    doc.add_paragraph()

    add_callout(
        "Overall Experiment Summary: TestSphere.AI achieved 100% recall in four of the five evaluated scenarios. The notification scenario achieved 82.3% recall, with 29 affected tests not selected. Additionally, high false positive rates (584 to 796 tests) reflect a conservative safety-first design that prioritizes test execution safety over maximum speed savings.",
        title="EXPERIMENT OBSERVATIONS & ACCURATE RECALL SUMMARY"
    )

    # ---------------------------------------------------------
    # 10. SECURITY AND ROLLBACK MANAGEMENT
    # ---------------------------------------------------------
    add_h1("10. Security, Access Control & Strategy Rollback")
    doc.add_paragraph(
        "• Configuration Protection: `config.json` containing local development credentials is ignored via `.gitignore`. A template file `config.example.json` provides safe placeholder values (`CHANGE_ME_LOCAL_ONLY`)."
    )
    doc.add_paragraph(
        "• Role-Based Access Control (RBAC): `Security/auth.py` enforces role permissions:"
    )
    doc.add_paragraph("  - ADMIN: Full administrative access (uploads, change registration, strategy rollback).")
    doc.add_paragraph("  - QA_ENGINEER: Test selection execution and change analysis access.")
    doc.add_paragraph("  - VIEWER: Read-only access. Attempting unauthorized modifications returns HTTP 403 Forbidden.")
    doc.add_paragraph(
        "• Protected API Endpoints: Requests to protected REST routes without valid session authentication return HTTP 401 Unauthorized."
    )
    doc.add_paragraph(
        "• Strategy Rollback Workflow: If QA leads observe pipeline issues during `SMART_SELECTOR` execution, calling `/api/strategy/rollback` updates `strategy_config` to `LEGACY_FULL_SUITE`, reverting the system to 100% full regression testing. Rollback actions are recorded in the rollback_history table and are accompanied by audit logging."
    )

    # ---------------------------------------------------------
    # 11. TESTING AND VERIFICATION
    # ---------------------------------------------------------
    add_h1("11. Testing & Verification")
    doc.add_paragraph(
        "System functionality was verified using Pytest across automated test scripts in the `Tests/` directory. During testing, 52 automated tests passed with no test failures. Two non-blocking configuration warnings were noted during test runs: a pytest-asyncio event-loop configuration warning and a FastAPI `@app.on_event` deprecation warning."
    )

    # ---------------------------------------------------------
    # 12. CURRENT 35% COMPLETION STATUS TABLE
    # ---------------------------------------------------------
    add_h1("12. Current 35% Completion Status")
    
    st_tbl = doc.add_table(rows=14, cols=3)
    st_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    st_headers = ["Project Component", "Completion Status", "Implementation Evidence"]
    for i, h in enumerate(st_headers):
        cell = st_tbl.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].font.bold = True
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        set_cell_background(cell, "1B365D")
        set_cell_margins(cell, top=80, bottom=80, left=100, right=100)

    status_data = [
        ("Problem & Requirements Analysis", "Completed", "Documented in project specifications and README.md"),
        ("Architecture & DAL Design", "Completed", "FastAPI API routes, Engine DAL, SQLite database schema"),
        ("Synthetic Dataset Generation", "Completed", "`Data_Generation/generate_dataset.py` (1000 tests, 84 deps)"),
        ("Change & Dependency Analysis", "Completed", "`Engine/change_analyzer.py`, `Engine/dependency_analyzer.py`"),
        ("Coverage & Failure Mapping", "Completed", "`Engine/coverage_analyzer.py`, `Engine/failure_analyzer.py`"),
        ("Additive Risk Scoring Engine", "Completed", "`Engine/risk_scorer.py` (+40 cov, +30 dep, +25 critical module)"),
        ("Safety Override Framework", "Completed", "`Engine/safety_overrides.py` (7 mandatory safety rules)"),
        ("Ground Truth & Benchmarking", "Completed", "Controlled scenario ground truths in `experiment_ground_truth`"),
        ("RBAC & Credential Isolation", "Completed", "`Security/auth.py`, `.gitignore` config rules, HTTP 401/403"),
        ("Strategy Rollback & Audit Log", "Completed", "`Rollback/rollback_manager.py`, `rollback_history` table"),
        ("Automated Testing Suite", "Completed", "52 passed automated tests in `Tests/` directory"),
        ("Stakeholder Live Validation", "Pending (DATA REQUIRED)", "Feedback form/API implemented; survey responses pending"),
        ("Advanced ML Optimization", "Planned (Future Phase)", "Roadmap item for Phase 2/3 development")
    ]
    for r_idx, row in enumerate(status_data, start=1):
        r_cells = st_tbl.rows[r_idx].cells
        for c_idx, val in enumerate(row):
            r_cells[c_idx].text = val
            set_cell_background(r_cells[c_idx], "F4F6F9" if r_idx % 2 == 1 else "FFFFFF")
            set_cell_margins(r_cells[c_idx], top=60, bottom=60, left=100, right=100)

    doc.add_paragraph()

    # ---------------------------------------------------------
    # 13. IDENTIFIED LIMITATIONS & STAKEHOLDER VALIDATION
    # ---------------------------------------------------------
    add_h1("13. Identified Limitations & Stakeholder Validation")
    add_h2("13.1 System Limitations")
    doc.add_paragraph("1. Synthetic Ground Truth: Evaluation relies on synthetically generated ground truth using controlled scenario rules and seeded/randomized associations for prototype evaluation rather than production repository history.")
    doc.add_paragraph("2. Notification Scenario False Negatives: Scenario CHG011 produced 29 false negatives (82.3% recall), demonstrating a need to refine scoring and dependency signals for non-critical modules.")
    doc.add_paragraph("3. Conservative Selection (High False Positives): High safety margins cause 584 to 796 false positives per run, prioritizing test execution safety over maximum speed savings.")
    doc.add_paragraph("These limitations are treated as development findings rather than hidden from the evaluation.")

    add_h2("13.2 Stakeholder Validation Status")
    doc.add_paragraph(
        "Stakeholder validation is currently marked **DATA REQUIRED**. While the feedback database schema (`feedback` table) and REST API endpoint (`/api/audit/feedback`) are functional, live user feedback responses have not yet been collected. No synthetic survey responses were created."
    )

    # ---------------------------------------------------------
    # 14. FUTURE WORK & CONCLUSION
    # ---------------------------------------------------------
    add_h1("14. Future Work & Conclusion")
    add_h2("14.1 Future Phase Roadmap")
    doc.add_paragraph("• Refine Notification Module Scoring: Adjust dependency weights and risk signals to resolve false negatives in CHG011.")
    doc.add_paragraph("• Reduce Unnecessary RUN Decisions: Optimize threshold tuning to improve precision without sacrificing safety.")
    doc.add_paragraph("• Collect Stakeholder Feedback: Execute user survey sessions with QA engineers to gather feedback data.")
    doc.add_paragraph("• Real Repository Integration: Connect the selection engine to actual Git commit hooks and CI pipelines.")

    add_h2("14.2 Conclusion")
    doc.add_paragraph(
        "At the current Review 1 stage, TestSphere.AI demonstrates a working change-impact test selection workflow across five controlled scenarios. The system achieved 100% recall in four scenarios, while the notification scenario achieved 82.3% recall. The experiments also show that the current safety-first strategy remains conservative, selecting many tests that are not classified as affected. These results provide a measurable baseline for further improvement during the remaining project phases."
    )

    # ---------------------------------------------------------
    # 15. REFERENCES & REPOSITORY LINK
    # ---------------------------------------------------------
    add_h1("15. References & Repository Link")
    doc.add_paragraph("1. FastAPI Documentation: https://fastapi.tiangolo.com/")
    doc.add_paragraph("2. SQLite Documentation: https://www.sqlite.org/docs.html")
    doc.add_paragraph("3. Official Project Repository: https://github.com/gowsick2007/TESTSPHERE-AI-MOBILE-BANKING")

    doc.add_page_break()

    # ---------------------------------------------------------
    # VIVA-READY DEFENSE GUIDE (20 COMMON QUESTIONS)
    # ---------------------------------------------------------
    add_h1("16. Viva-Ready Defense Guide (20 Common Questions)")
    
    viva_qas = [
        ("Q1: What problem does TestSphere.AI solve?", "It reduces continuous integration pipeline delays by selecting only impacted automated tests rather than running the full 1,000-test regression suite after every code change."),
        ("Q2: Why is full regression testing expensive?", "In our benchmark, executing 1,000 tests takes 2,238 seconds (~37.3 minutes). Running this on every minor commit consumes excessive time, CPU resources, and device cloud runtime."),
        ("Q3: What data does the system use?", "It uses commit metadata, file dependency graphs, test coverage maps, historical test failure logs (90 days), and mobile device risk levels."),
        ("Q4: How does change impact analysis work?", "It inspects modified source files, determines affected modules, and checks whether the change involves security-sensitive code like authentication or OTP."),
        ("Q5: What is dependency analysis?", "It traverses directional dependency edges in dependency_map to find files that depend on modified source code, ensuring transitively affected tests are identified."),
        ("Q6: How does risk scoring work?", "It uses an additive formula (+40 direct coverage, +30 dependency, +30 security, +25 critical module, +20 historical failure, +15 recent failure, +10 high-risk device). If score >= 50, the test is marked for RUN."),
        ("Q7: Why are safety overrides necessary?", "They ensure safety takes priority over speed. If data is missing (unknown dependency/coverage) or critical modules (Auth, Payment, OTP) are involved, the engine forces a RUN decision regardless of score."),
        ("Q8: What is a RUN decision?", "A decision indicating the test script should be executed in the current pipeline run because it is likely affected or required by safety rules."),
        ("Q9: What is a SKIP decision?", "A decision indicating the test script is unlikely to be affected by the current change and can be safely omitted under the active strategy."),
        ("Q10: What is the baseline?", "The Legacy Full Suite Baseline where all 1,000 tests are executed on every build, taking 2,238.33 seconds."),
        ("Q11: What does precision mean in this project?", "The percentage of selected RUN tests that were actually affected (TP / (TP + FP)). Precision is relatively low (11.4% - 21.8%) because the system intentionally selects extra tests for safety."),
        ("Q12: What does recall mean in this project?", "The percentage of actually affected tests that were correctly selected to RUN (TP / (TP + FN)). High recall means fewer missed defects."),
        ("Q13: Why is recall important?", "In mobile banking, a false negative (skipping an affected test) risks deploying a bug to production, whereas a false positive (running an unaffected test) only costs minor execution time."),
        ("Q14: Why did CHG011 achieve only 82.3% recall?", "The notification scenario produced 29 false negatives. These affected tests were not selected by the current scoring and safety rules, indicating that the dependency and risk signals for the notification module need further investigation and refinement in the next phase."),
        ("Q15: Why are there many false positives?", "Because our safety rules force RUN decisions for critical modules and missing data, preferring extra test execution over risking missed bugs."),
        ("Q16: Is the ground truth real or synthetic?", "Ground truth data was synthetically generated using controlled scenario rules and seeded/randomized associations for prototype evaluation, not real production banking test history."),
        ("Q17: Is machine learning currently implemented?", "No. Phase 1 relies on transparent rule-based risk scoring and graph analysis. ML model optimization is planned as a future enhancement."),
        ("Q18: What has been completed at 35%?", "FastAPI backend, SQLite database, web UI, change/dependency analysis, risk scoring, safety overrides, RBAC security, rollback workflow, 52 passing Pytest tests, and initial experiment evaluation."),
        ("Q19: What remains for the final phase?", "Refining non-critical module recall (CHG011), collecting genuine stakeholder survey responses, improving precision, and integrating real Git commit hooks."),
        ("Q20: What is the main contribution of the project?", "Establishing a transparent, rule-based, and auditable change-impact test selection prototype that reduces test execution time while enforcing strict safety controls for banking applications.")
    ]

    for q, a in viva_qas:
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(4)
        p_q.paragraph_format.space_after = Pt(1)
        r_q = p_q.add_run(q)
        r_q.bold = True
        r_q.font.color.rgb = PRIMARY_COLOR
        
        p_a = doc.add_paragraph()
        p_a.paragraph_format.space_before = Pt(0)
        p_a.paragraph_format.space_after = Pt(4)
        r_a = p_a.add_run(a)
        r_a.font.size = Pt(10.5)

    # Save DOCX document
    out_dir = "docs"
    os.makedirs(out_dir, exist_ok=True)
    out_path_docx = os.path.join(out_dir, "TestSphere_AI_Semester5_Review1_Report.docx")
    doc.save(out_path_docx)
    print(f"DOCX Report generated successfully at: {out_path_docx}")

    # Generate matching Markdown file at docs/TestSphere_AI_Semester5_Review1_Report.md
    md_content = """# TestSphere.AI – Change Impact Test Selector for Mobile Banking Applications

**C28 Semester 5 Project — Review 1 Report (35% Completion Milestone)**

---

## Metadata & Project Details

- **Project Title:** TestSphere.AI – Change Impact Test Selector for Mobile Banking Applications
- **Course & Academic Phase:** C28 Semester 5 Project — Review 1 (2025–2026)
- **Project Completion Milestone:** 35% Completed
- **Official GitHub Repository:** https://github.com/gowsick2007/TESTSPHERE-AI-MOBILE-BANKING
- **Core Stack:** FastAPI (Python), SQLite3, HTML5/CSS3/JavaScript (Dark-Fintech Glassmorphism Theme), Pytest
- **Primary Project Domain:** Data Science / Intelligent Software Test Selection

---

## Abstract

Mobile banking applications require frequent software updates for security patches, feature enhancements, and bug fixes across functional modules like Payment, Authentication, Transaction Processing, and Notifications. Running a full regression suite after every small code edit introduces significant pipeline latency. This project report presents the Review 1 (35% completion) status of **TestSphere.AI**, a data-driven change-impact test selection system for mobile banking software.

TestSphere.AI analyzes code change metadata, file dependency graphs, test coverage maps, historical test failure logs, and mobile hardware risk levels to classify automated tests into **RUN** and **SKIP** decisions. The selector relies on an additive risk-scoring formula combined with seven mandatory safety overrides that prioritize test safety over aggressive skipping. Ground truth data was synthetically generated using controlled scenario rules and seeded/randomized associations for prototype evaluation. In baseline benchmarking against a 1,000-test synthetic regression suite (full execution time of 2,238.33 seconds / ~37.3 minutes), TestSphere.AI demonstrated execution time reductions ranging from 5.1% to 23.4%. TestSphere.AI achieved 100% recall in four of the five evaluated scenarios. The notification scenario achieved 82.3% recall, with 29 affected tests not selected. This report details the system architecture, dataset design, scoring logic, security controls, strategy rollback, and initial experimental evaluation.

---

## 1. Introduction

Continuous integration and continuous delivery (CI/CD) pipelines rely heavily on automated regression testing to prevent software defects from reaching production environments. In mobile banking software, quality assurance is critical because application bugs can lead to security vulnerabilities, transaction failures, compliance breaches, and user dissatisfaction.

As mobile banking projects expand, QA teams accumulate large suites of automated test scripts to cover various user journeys, API endpoints, and mobile device configurations. However, running a complete 1,000-test suite for small code changes (such as fixing a typo in a login validation label or tweaking a notification text color) consumes unnecessary time and hardware resources. TestSphere.AI addresses this bottleneck by evaluating code changes and selecting only the tests that are likely to be affected, while maintaining safety rules to protect critical banking functions.

---

## 2. Problem Statement

Mobile banking CI/CD pipelines face two opposing challenges:
1. **Pipeline Latency:** Running full regression suites after every minor commit causes feedback delays for developers, taking over 37 minutes per build in our benchmark.
2. **Defect Risk:** Skipping tests manually or randomly risks missing regression bugs in critical financial paths like payments or authentication.

The main problem identified during early project planning was the lack of an automated, transparent mechanism to identify affected tests based on objective repository data. TestSphere.AI was developed to provide a data-driven test selection workflow that balances testing speed with safety.

---

## 3. Project Objectives

The primary technical goals for the Review 1 (35% completion) milestone were:
- Design a modular system architecture combining a FastAPI backend, SQLite database, and web frontend.
- Build a synthetic data generation pipeline to seed test coverage maps, file dependency graphs, device matrices, and failure logs.
- Implement an additive, rule-based risk-scoring engine (+40 coverage, +30 dependency, +30 security, +25 critical module, +20 historical failure, +15 recent failure, +10 high-risk device).
- Enforce seven mandatory safety overrides to force RUN decisions when data is missing or critical modules are involved.
- Implement Role-Based Access Control (RBAC), configuration isolation, audit logging, and strategy rollback capabilities.
- Evaluate selector performance across five controlled experiment scenarios using precision, recall, and runtime reduction metrics.

---

## 4. Data Science Approach & Scope

TestSphere.AI is primarily a Data Science / Intelligent Test Selection project supported by standard web software engineering components. Rather than relying on black-box machine learning models at this stage, the data science approach centers on exploratory data analysis, graph dependency traversal, multi-factor risk weighting, and precision/recall performance evaluation.

The current implementation processes structured datasets (coverage maps, dependency edges, historical execution logs) to calculate evidence-based risk scores for each test. Machine learning optimization is planned as a future enhancement for Phase 2, while the current Phase 1 foundation focuses on transparent data analytical reasoning.

---

## 5. Existing Practice vs. Proposed System

| Dimension | Existing Practice (Full Suite / Manual) | Proposed System (TestSphere.AI) |
| :--- | :--- | :--- |
| **Execution Strategy** | Executes 1000/1000 tests on every commit, or relies on manual unguided filtering. | Analyzes commit changes and executes impacted tests while skipping unimpacted ones. |
| **Pipeline Feedback Time** | Slow (approx. 37.3 minutes per build). | Faster (approx. 28.6 to 35.2 minutes per build, reducing runtime by up to 23.4%). |
| **Decision Safety** | No explicit safety checks; manual skips risk missing critical tests. | Enforces 7 mandatory safety overrides (forced RUN for security, critical modules, missing data). |
| **Audit & Control** | No audit log or instant recovery mechanism. | RBAC enforcement, central audit logging, and instant strategy rollback to full suite. |

---

## 6. System Architecture & Core Modules

TestSphere.AI uses a tiered architecture where the web frontend interacts with FastAPI REST endpoints, which delegate business logic to core engine modules and the Data Access Layer (DAL).

> **Architecture Flow:**  
> Frontend (HTML/CSS/JS UI) → FastAPI Backend (`backend/api/`) → Selection Engine (`Engine/test_selector.py`) → Data Access Layer (`Engine/data_access.py`) → SQLite Database (`Data/testsphere.db`)

### Core Engine Components:
- `Engine/change_analyzer.py`: Parses changed file paths, identifies affected modules, and checks security sensitivity.
- `Engine/dependency_analyzer.py`: Traverses direct and transitive file dependency edges in `dependency_map`.
- `Engine/coverage_analyzer.py`: Maps impacted source files to test scripts in `test_coverage`.
- `Engine/failure_analyzer.py`: Checks test execution failure history over the last 90 days.
- `Engine/risk_scorer.py`: Computes additive risk scores for each test script.
- `Engine/safety_overrides.py`: Evaluates seven mandatory safety rules to force RUN decisions.
- `Engine/rationale_generator.py`: Generates human-readable explanations for selection decisions.
- `Rollback/rollback_manager.py`: Manages strategy state (`SMART_SELECTOR` vs `LEGACY_FULL_SUITE`) and records rollback events.
- `Security/auth.py`: Handles session authentication, password hashing, and role checks (ADMIN, QA_ENGINEER, VIEWER).

---

## 7. Dataset & Data Preparation

To enable controlled experimentation without requiring proprietary banking repository data, TestSphere.AI includes an automated dataset generation module (`Data_Generation/generate_dataset.py`). The generator populates the SQLite database with synthetic records for testing.

> **Synthetic Ground Truth Clarification:** Ground truth records in `experiment_ground_truth` are synthetically generated using controlled scenario rules and seeded/randomized associations. They were created specifically for evaluating the prototype selection logic in controlled change scenarios and are NOT claimed to represent real production banking test history.

| Table Name | Record Count / Nature | Functional Purpose |
| :--- | :--- | :--- |
| `test_coverage` | 1,000 rows | Stores test script metadata, target file paths, modules, devices, and execution times. |
| `dependency_map` | 84 rows | Defines directional source file dependency edges (`source_file` → `depends_on`). |
| `failure_history` | 2,400 rows | Contains historical test failure records over the past 90 days. |
| `device_matrix` | 8 rows | Mobile device profiles with hardware risk levels (Pixel 8, iPhone 15, etc.). |
| `code_changes` | 15 rows | Recorded commit change entries with module classifications and risk tags. |
| `experiment_ground_truth` | Scenario-generated mappings, with up to 5,000 mappings possible across the five controlled scenarios. | Contains scenario-generated experiment ground truth mappings for change impact benchmarking. |
| `selection_results` | Dynamic | Stores engine test selection decisions and generated rationale strings. |
| `strategy_config` | 1 active row | Active selection strategy state (`SMART_SELECTOR` vs `LEGACY_FULL_SUITE`). |
| `rollback_history` | Audit rows | Audit records tracking strategy rollback events, users, timestamps, and reasons. |
| `feedback` | 0 rows (`DATA REQUIRED`) | Survey schema (Q1-Q5 ratings) for collecting stakeholder feedback. |
| `audit_log` | Audit rows | System security log tracking user logins, file uploads, and strategy updates. |

---

## 8. Risk Scoring & Safety Overrides

### 8.1 Additive Risk Scoring Mechanics
The risk scoring module (`Engine/risk_scorer.py`) calculates a numerical risk score for each test script by evaluating seven weighted factors:
- **Direct Coverage (+40 points):** Test script directly targets a file modified in the commit.
- **Dependency Path (+30 points):** Test covers a file linked via the dependency graph.
- **Security-Sensitive Change (+30 points):** Commit involves security, authentication, or encryption code.
- **Critical Banking Module (+25 points):** Test belongs to Authentication, Payment, or OTP modules.
- **Historical Failure (+20 points):** Test module has recorded past failures in `failure_history`.
- **Recent Failure (+15 points):** Test script has failed within the last 90 days.
- **High-Risk Device (+10 points):** Test targets high-risk mobile hardware/OS profiles.

**Decision Rule:** RUN_THRESHOLD = 50. A test is marked for RUN when its calculated score is greater than or equal to 50. Otherwise, it is marked for SKIP.

### 8.2 Mandatory Safety Overrides
To ensure test safety takes precedence over speed, `Engine/safety_overrides.py` enforces seven explicit safety rules that force a RUN decision regardless of numeric score:
1. **Rule 1 (Unknown Dependency):** Triggered when dependency graph data is missing. Forces RUN to avoid missing unmapped dependencies.
2. **Rule 2 (Unknown Coverage):** Triggered when test coverage data is unavailable. Forces RUN to ensure unmapped tests execute.
3. **Rule 3 (Security Critical):** Triggered when a test is marked `is_security_critical=1`. Forces RUN to protect security paths.
4. **Rule 4 (Critical Banking Module):** Triggered when changes touch Authentication, Payment, or OTP modules. Forces RUN for core financial logic.
5. **Rule 5 (No Failure Data):** Triggered when historical failure logs are absent. Forces RUN as a safe fallback.
6. **Rule 6 (Low Confidence):** Triggered when engine confidence falls below 0.5. Forces RUN under uncertainty.
7. **Rule 7 (Rationale Requirement):** Requires every test skip decision to generate a detailed explanation, preventing unexplained test drops.

---

## 9. Experimental Results & Benchmarking

We evaluated TestSphere.AI across five controlled commit scenarios comparing Smart Selection against a Legacy Full Suite Baseline (1,000 tests, execution time 2,238.33 seconds / ~37.3 minutes).

| Scenario | Changed File | Total | Affected | RUN | SKIP | TP | TN | FP | FN | Recall | Time Red. |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **CHG001 Payment** | `payment/payment.py` | 1000 | 125 | 921 | 79 | 125 | 79 | 796 | 0 | 100.0% | 5.7% |
| **CHG003 Auth** | `auth/login.py` | 1000 | 90 | 674 | 326 | 90 | 326 | 584 | 0 | 100.0% | 23.4% |
| **CHG008 Transfer** | `transaction/txn_limit.py` | 1000 | 96 | 842 | 158 | 96 | 158 | 746 | 0 | 100.0% | 11.3% |
| **CHG011 Push Notif.** | `notification/push.py` | 1000 | 164 | 927 | 73 | 135 | 44 | 792 | 29 | 82.3% | 5.1% |
| **CHG_MULTI Multi-File** | `payment.py` + `login.py` | 1000 | 181 | 830 | 170 | 181 | 170 | 649 | 0 | 100.0% | 11.7% |

> **Overall Experiment Summary:** TestSphere.AI achieved 100% recall in four of the five evaluated scenarios. The notification scenario achieved 82.3% recall, with 29 affected tests not selected. Additionally, high false positive rates (584 to 796 tests) reflect a conservative safety-first design that prioritizes test execution safety over maximum speed savings.

---

## 10. Security, Access Control & Strategy Rollback

- **Configuration Protection:** `config.json` containing local development credentials is ignored via `.gitignore`. A template file `config.example.json` provides safe placeholder values (`CHANGE_ME_LOCAL_ONLY`).
- **Role-Based Access Control (RBAC):** `Security/auth.py` enforces role permissions:
  - **ADMIN:** Full administrative access (uploads, change registration, strategy rollback).
  - **QA_ENGINEER:** Test selection execution and change analysis access.
  - **VIEWER:** Read-only access. Attempting unauthorized modifications returns HTTP 403 Forbidden.
- **Protected API Endpoints:** Requests to protected REST routes without valid session authentication return HTTP 401 Unauthorized.
- **Strategy Rollback Workflow:** If QA leads observe pipeline issues during `SMART_SELECTOR` execution, calling `/api/strategy/rollback` updates `strategy_config` to `LEGACY_FULL_SUITE`, reverting the system to 100% full regression testing. Rollback actions are recorded in the rollback_history table and are accompanied by audit logging.

---

## 11. Testing & Verification

System functionality was verified using Pytest across automated test scripts in the `Tests/` directory. During testing, 52 automated tests passed with no test failures. Two non-blocking configuration warnings were noted during test runs: a pytest-asyncio event-loop configuration warning and a FastAPI `@app.on_event` deprecation warning.

---

## 12. Current 35% Completion Status

| Project Component | Completion Status | Implementation Evidence |
| :--- | :--- | :--- |
| **Problem & Requirements Analysis** | Completed | Documented in project specifications and README.md |
| **Architecture & DAL Design** | Completed | FastAPI API routes, Engine DAL, SQLite database schema |
| **Synthetic Dataset Generation** | Completed | `Data_Generation/generate_dataset.py` (1000 tests, 84 deps) |
| **Change & Dependency Analysis** | Completed | `Engine/change_analyzer.py`, `Engine/dependency_analyzer.py` |
| **Coverage & Failure Mapping** | Completed | `Engine/coverage_analyzer.py`, `Engine/failure_analyzer.py` |
| **Additive Risk Scoring Engine** | Completed | `Engine/risk_scorer.py` (+40 cov, +30 dep, +25 critical module) |
| **Safety Override Framework** | Completed | `Engine/safety_overrides.py` (7 mandatory safety rules) |
| **Ground Truth & Benchmarking** | Completed | Controlled scenario ground truths in `experiment_ground_truth` |
| **RBAC & Credential Isolation** | Completed | `Security/auth.py`, `.gitignore` config rules, HTTP 401/403 |
| **Strategy Rollback & Audit Log** | Completed | `Rollback/rollback_manager.py`, `rollback_history` table |
| **Automated Testing Suite** | Completed | 52 passed automated tests in `Tests/` directory |
| **Stakeholder Live Validation** | Pending (`DATA REQUIRED`) | Feedback form/API implemented; survey responses pending |
| **Advanced ML Optimization** | Planned (Future Phase) | Roadmap item for Phase 2/3 development |

---

## 13. Identified Limitations & Stakeholder Validation

### 13.1 System Limitations
1. **Synthetic Ground Truth:** Evaluation relies on synthetically generated ground truth using controlled scenario rules and seeded/randomized associations for prototype evaluation rather than production repository history.
2. **Notification Scenario False Negatives:** Scenario CHG011 produced 29 false negatives (82.3% recall), demonstrating a need to refine scoring and dependency signals for non-critical modules.
3. **Conservative Selection (High False Positives):** High safety margins cause 584 to 796 false positives per run, prioritizing test execution safety over maximum speed savings.

These limitations are treated as development findings rather than hidden from the evaluation.

### 13.2 Stakeholder Validation Status
Stakeholder validation is currently marked **DATA REQUIRED**. While the feedback database schema (`feedback` table) and REST API endpoint (`/api/audit/feedback`) are functional, live user feedback responses have not yet been collected. No synthetic survey responses were created.

---

## 14. Future Work & Conclusion

### 14.1 Future Phase Roadmap
- **Refine Notification Module Scoring:** Adjust dependency weights and risk signals to resolve false negatives in CHG011.
- **Reduce Unnecessary RUN Decisions:** Optimize threshold tuning to improve precision without sacrificing safety.
- **Collect Stakeholder Feedback:** Execute user survey sessions with QA engineers to gather feedback data.
- **Real Repository Integration:** Connect the selection engine to actual Git commit hooks and CI pipelines.

### 14.2 Conclusion
At the current Review 1 stage, TestSphere.AI demonstrates a working change-impact test selection workflow across five controlled scenarios. The system achieved 100% recall in four scenarios, while the notification scenario achieved 82.3% recall. The experiments also show that the current safety-first strategy remains conservative, selecting many tests that are not classified as affected. These results provide a measurable baseline for further improvement during the remaining project phases.

---

## 15. References & Repository Link

1. **FastAPI Documentation:** https://fastapi.tiangolo.com/
2. **SQLite Documentation:** https://www.sqlite.org/docs.html
3. **Official Project Repository:** https://github.com/gowsick2007/TESTSPHERE-AI-MOBILE-BANKING

---

## 16. Viva-Ready Defense Guide (20 Common Questions)

**Q1: What problem does TestSphere.AI solve?**  
*Answer:* It reduces continuous integration pipeline delays by selecting only impacted automated tests rather than running the full 1,000-test regression suite after every code change.

**Q2: Why is full regression testing expensive?**  
*Answer:* In our benchmark, executing 1,000 tests takes 2,238 seconds (~37.3 minutes). Running this on every minor commit consumes excessive time, CPU resources, and device cloud runtime.

**Q3: What data does the system use?**  
*Answer:* It uses commit metadata, file dependency graphs, test coverage maps, historical test failure logs (90 days), and mobile device risk levels.

**Q4: How does change impact analysis work?**  
*Answer:* It inspects modified source files, determines affected modules, and checks whether the change involves security-sensitive code like authentication or OTP.

**Q5: What is dependency analysis?**  
*Answer:* It traverses directional dependency edges in `dependency_map` to find files that depend on modified source code, ensuring transitively affected tests are identified.

**Q6: How does risk scoring work?**  
*Answer:* It uses an additive formula (+40 direct coverage, +30 dependency, +30 security, +25 critical module, +20 historical failure, +15 recent failure, +10 high-risk device). If score >= 50, the test is marked for RUN.

**Q7: Why are safety overrides necessary?**  
*Answer:* They ensure safety takes priority over speed. If data is missing (unknown dependency/coverage) or critical modules (Auth, Payment, OTP) are involved, the engine forces a RUN decision regardless of score.

**Q8: What is a RUN decision?**  
*Answer:* A decision indicating the test script should be executed in the current pipeline run because it is likely affected or required by safety rules.

**Q9: What is a SKIP decision?**  
*Answer:* A decision indicating the test script is unlikely to be affected by the current change and can be safely omitted under the active strategy.

**Q10: What is the baseline?**  
*Answer:* The Legacy Full Suite Baseline where all 1,000 tests are executed on every build, taking 2,238.33 seconds.

**Q11: What does precision mean in this project?**  
*Answer:* The percentage of selected RUN tests that were actually affected (TP / (TP + FP)). Precision is relatively low (11.4% - 21.8%) because the system intentionally selects extra tests for safety.

**Q12: What does recall mean in this project?**  
*Answer:* The percentage of actually affected tests that were correctly selected to RUN (TP / (TP + FN)). High recall means fewer missed defects.

**Q13: Why is recall important?**  
*Answer:* In mobile banking, a false negative (skipping an affected test) risks deploying a bug to production, whereas a false positive (running an unaffected test) only costs minor execution time.

**Q14: Why did CHG011 achieve only 82.3% recall?**  
*Answer:* The notification scenario produced 29 false negatives. These affected tests were not selected by the current scoring and safety rules, indicating that the dependency and risk signals for the notification module need further investigation and refinement in the next phase.

**Q15: Why are there many false positives?**  
*Answer:* Because our safety rules force RUN decisions for critical modules and missing data, preferring extra test execution over risking missed bugs.

**Q16: Is the ground truth real or synthetic?**  
*Answer:* Ground truth data was synthetically generated using controlled scenario rules and seeded/randomized associations for prototype evaluation, not real production banking test history.

**Q17: Is machine learning currently implemented?**  
*Answer:* No. Phase 1 relies on transparent rule-based risk scoring and graph analysis. ML model optimization is planned as a future enhancement.

**Q18: What has been completed at 35%?**  
*Answer:* FastAPI backend, SQLite database, web UI, change/dependency analysis, risk scoring, safety overrides, RBAC security, rollback workflow, 52 passing Pytest tests, and initial experiment evaluation.

**Q19: What remains for the final phase?**  
*Answer:* Refining non-critical module recall (CHG011), collecting genuine stakeholder survey responses, improving precision, and integrating real Git commit hooks.

**Q20: What is the main contribution of the project?**  
*Answer:* Establishing a transparent, rule-based, and auditable change-impact test selection prototype that reduces test execution time while enforcing strict safety controls for banking applications.
"""
    out_path_md = os.path.join(out_dir, "TestSphere_AI_Semester5_Review1_Report.md")
    with open(out_path_md, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Markdown Report saved successfully at: {out_path_md}")

if __name__ == "__main__":
    create_report()
