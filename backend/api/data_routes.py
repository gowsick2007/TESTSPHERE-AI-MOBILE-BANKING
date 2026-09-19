"""
TestSphere AI — Data Management Routes
Handles CSV uploads, validation, download templates, and database resets.
"""
import io
import json
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response
from fastapi.responses import StreamingResponse
from typing import Optional
from backend.database import get_db_connection
from backend.engine.data_access import (
    get_data_health, clear_table, upsert_dataset_metadata, get_dataset_metadata
)
from backend.security.input_validator import validate_csv_content, detect_bypass_attempt
from backend.security.csv_validator import (
    parse_and_validate_csv, parse_and_validate_full_csv, get_storage_paths,
    _enrich_for_sqlite
)
from backend.api.auth_routes import get_user_from_token
from backend.engine.audit_logger import log_event
from Data_Generation.generate_dataset import generate_and_load
from backend.engine.dependency_analyzer import clear_dependency_graph_cache as clear_be_cache
from Engine.dependency_analyzer import clear_dependency_graph_cache as clear_eng_cache

router = APIRouter(prefix="/data", tags=["Data Management"])


@router.get("/status")
def get_status():
    """Get metadata and counts for all datasets."""
    health = get_data_health()
    meta = get_dataset_metadata()
    return {"health": health, "metadata": meta}


@router.post("/upload/full")
async def upload_full_dataset(
    file: UploadFile = File(...),
    user: dict = Depends(get_user_from_token),
    commit: bool = True,
    mapping: Optional[str] = None
):
    role = user["role"]

    # Enforce backend role check
    blocked, msg = detect_bypass_attempt("IMPORT_DATA", "Upload Full Dataset", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    content = await file.read()
    
    # Parse custom mapping from JSON if provided
    user_mapping = None
    if mapping:
        try:
            user_mapping = json.loads(mapping)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid mapping JSON format.")

    # Call new validation and cleaning pipeline for the full dataset
    report = parse_and_validate_full_csv(
        file_content=content,
        original_filename=file.filename,
        user_mapping=user_mapping,
        commit=commit
    )

    if not report["success"]:
        # Return validation report in HTTP 400 detail so frontend can parse and display it
        raise HTTPException(status_code=400, detail=report)

    if not commit:
        # Step 1: Return report directly
        report_out = report.copy()
        report_out.pop("_cleaned_dfs", None)
        return report_out

    if not report["is_valid_to_save"]:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": f"Cannot import dataset because status is {report['status']}.",
                "report": report
            }
        )

    # Save to SQLite using a transaction
    cleaned_dfs = report.get("_cleaned_dfs", {})
    conn = get_db_connection()
    updated_tables = []
    import_ts = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- Pre-import SQLite schema enrichment (API-level safety net) ---
    # parse_and_validate_full_csv already does this when commit=True from within
    # the validator.  This ensures the same protection when the API calls with
    # pre-built cleaned_dfs (e.g. after a two-step review-then-commit flow).
    enrich_issues = []
    for g in list(cleaned_dfs.keys()):
        if report["coverage"].get(g) == "DETECTED":
            enriched_df, errs = _enrich_for_sqlite(g, cleaned_dfs[g], import_ts)
            if errs:
                enrich_issues.extend([f"[{g}] {e}" for e in errs])
            else:
                cleaned_dfs[g] = enriched_df

    if enrich_issues:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "status": "NEEDS_REVIEW",
                "stage": "DATABASE_VALIDATION",
                "message": (
                    "Dataset could not be imported because required database fields "
                    "could not be safely resolved."
                ),
                "issues": enrich_issues,
            }
        )

    try:
        conn.execute("BEGIN TRANSACTION")
        # Insert records into SQLite for each detected group
        for g, df_clean in cleaned_dfs.items():
            if report["coverage"].get(g) == "DETECTED":
                # Clear existing table first (Replace policy)
                conn.execute(f"DELETE FROM {g}")
                # Insert records using pandas to_sql
                df_clean.to_sql(name=g, con=conn, if_exists="append", index=False)
                updated_tables.append(g)

        conn.commit()

        # Update version metadata outside of database transaction (it manages its own conn)
        for g in updated_tables:
            upsert_dataset_metadata(g, len(cleaned_dfs[g]), file.filename)

        # Clear dependency graph caches
        clear_be_cache()
        clear_eng_cache()

        # Log event
        log_event(
            action="UPLOAD_FULL_DATASET",
            username=user["username"],
            input_summary=f"Uploaded {file.filename} (Imported groups: {', '.join(updated_tables)})",
            result="SUCCESS"
        )
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        # Return a structured, user-friendly error — never expose raw SQLite internals.
        exc_str = str(exc)
        friendly = _friendly_db_error(exc_str)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "status": "IMPORT_FAILED",
                "stage": "DATABASE_TRANSACTION",
                "message": friendly,
                "technical_detail": exc_str,
            }
        )
    finally:
        conn.close()

    report_out = report.copy()
    report_out.pop("_cleaned_dfs", None)

    return {
        "success": True,
        "message": "Dataset imported successfully.",
        "updated_tables": updated_tables,
        "report": report_out
    }


@router.post("/upload/{dataset_type}")
async def upload_dataset(
    dataset_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_user_from_token),
    commit: bool = True,
    mapping: Optional[str] = None
):
    role = user["role"]

    # Enforce backend role check
    blocked, msg = detect_bypass_attempt("IMPORT_DATA", f"Upload {dataset_type}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    content = await file.read()
    
    # Parse custom mapping from JSON if provided
    user_mapping = None
    if mapping:
        try:
            user_mapping = json.loads(mapping)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid mapping JSON format.")

    # Call new validation and cleaning pipeline
    report = parse_and_validate_csv(
        dataset_type=dataset_type,
        file_content=content,
        original_filename=file.filename,
        user_mapping=user_mapping,
        commit=commit
    )

    if not report["success"] or not report["is_valid_to_save"]:
        # Return validation report in HTTP 400 detail so frontend can parse and display it
        raise HTTPException(status_code=400, detail=report)

    if not commit:
        # Step 1: Return report directly
        return report

    # Step 2: Save to SQLite (Since validation succeeded and commit=True, cleaned data is stored)
    raw_path, clean_path = get_storage_paths(dataset_type, file.filename)
    try:
        df_clean = pd.read_csv(clean_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read cleaned data from file: {str(exc)}")

    conn = get_db_connection()
    try:
        # Clear existing table first (Replace policy)
        conn.execute(f"DELETE FROM {dataset_type}")
        # Insert records using pandas to_sql
        df_clean.to_sql(name=dataset_type, con=conn, if_exists="append", index=False)
        conn.commit()

        # Update version metadata
        upsert_dataset_metadata(dataset_type, len(df_clean), file.filename)

        # Clear dependency graph caches
        clear_be_cache()
        clear_eng_cache()

        # Log event
        log_event(
            action="UPLOAD_DATASET",
            username=user["username"],
            input_summary=f"Uploaded {file.filename} to {dataset_type} ({len(df_clean)} records)",
            result="SUCCESS"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database import failed: {str(exc)}")
    finally:
        conn.close()

    return {
        "success": True,
        "message": f"Successfully imported {len(df_clean)} records into {dataset_type}.",
        "records": len(df_clean),
        "report": report
    }


@router.post("/demo")
def load_demo(user: dict = Depends(get_user_from_token)):
    role = user["role"]

    blocked, msg = detect_bypass_attempt("LOAD_DEMO", "Generate demo dataset", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    try:
        summary = generate_and_load(verbose=False)
        clear_be_cache()
        clear_eng_cache()
        log_event(
            action="LOAD_DEMO",
            username=user["username"],
            input_summary="Loaded synthetic demo dataset (1000+ tests)",
            result="SUCCESS"
        )
        return {"success": True, "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate demo data: {str(exc)}")


@router.delete("/{dataset_type}")
def delete_dataset(dataset_type: str, user: dict = Depends(get_user_from_token)):
    role = user["role"]

    blocked, msg = detect_bypass_attempt("CLEAR_DATASET", f"Clear {dataset_type}", role)
    if blocked:
        raise HTTPException(status_code=403, detail=msg)

    count = clear_table(dataset_type)
    clear_be_cache()
    clear_eng_cache()
    log_event(
        action="CLEAR_DATASET",
        username=user["username"],
        input_summary=f"Cleared all records from {dataset_type}",
        result="SUCCESS"
    )
    return {"success": True, "records_deleted": count}


@router.get("/{dataset_type}/download")
def download_dataset(dataset_type: str):
    """Allows downloading a dataset as a CSV file."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {dataset_type}", conn)
        # Drop primary key index columns if pandas added them
        if "id" in df.columns:
            df = df.drop(columns=["id"])

        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = Response(content=stream.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={dataset_type}.csv"
        return response
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Download compilation failed: {str(exc)}")
    finally:
        conn.close()


@router.get("/template/{dataset_type}")
def get_template(dataset_type: str):
    """Provides blank CSV templates with required headers."""
    columns_mapping = {
        "test_coverage": ["test_id", "test_name", "file_path", "module", "device", "os_version", "execution_time"],
        "dependency_map": ["source_file", "depends_on", "module"],
        "failure_history": ["test_id", "failure_date", "module", "device", "os_version", "severity"],
        "device_matrix": ["device_id", "device_name", "os_type", "os_version", "risk_level", "failure_rate"],
        "code_changes": ["change_id", "file_path", "module", "change_type", "risk_level"]
    }

    if dataset_type not in columns_mapping:
        raise HTTPException(status_code=404, detail="Template type not recognized.")

    df = pd.DataFrame(columns=columns_mapping[dataset_type])
    stream = io.StringIO()
    df.to_csv(stream, index=False)

    response = Response(content=stream.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={dataset_type}_template.csv"
    return response


@router.get("/{dataset_type}/preview")
def preview_dataset(dataset_type: str, limit: int = 50):
    """Preview the first 50 rows of a table."""
    conn = get_db_connection()
    try:
        rows = conn.execute(f"SELECT * FROM {dataset_type} LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def _friendly_db_error(exc_str: str) -> str:
    """Convert a raw SQLite exception string into a user-friendly message."""
    s = exc_str.lower()
    if "not null constraint" in s:
        # Extract the column name for a precise hint.
        import re
        m = re.search(r"not null constraint failed: (\S+)", exc_str, re.IGNORECASE)
        col = m.group(1) if m else "a required field"
        return (
            f"TestSphere.AI could not import the dataset because the field '{col}' "
            f"is required by the database but no value could be determined from the "
            f"source data. Please ensure the source CSV contains this field or an "
            f"accepted synonym."
        )
    if "unique constraint" in s:
        return (
            "The dataset contains duplicate records that conflict with existing database "
            "entries. Please deduplicate the source data and try again."
        )
    if "no such table" in s:
        return "The target database table does not exist. Please re-initialise the database."
    return (
        "An unexpected database error occurred during import. "
        "The transaction has been rolled back. No data was changed."
    )
