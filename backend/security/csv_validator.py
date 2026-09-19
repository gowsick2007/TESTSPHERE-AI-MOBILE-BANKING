"""
TestSphere AI — CSV Validation & Cleaning Pipeline
Validates file structures, checks schemas, handles column mapping,
performs data quality checks, cleans data in memory, and persists both raw and clean datasets.
"""
import io
import os
import re
import json
import logging
from datetime import datetime
from typing import Tuple, Dict, List, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Expected schemas for the 5 datasets
SCHEMAS = {
    "test_coverage": {
        "required": ["test_id", "test_name", "file_path", "module", "device", "os_version", "execution_time"],
        "unique_id": "test_id",
        "numeric": {"execution_time": {"min": 0.0, "default": 0.5}}
    },
    "dependency_map": {
        "required": ["source_file", "depends_on", "module"],
        "unique_id": None
    },
    "failure_history": {
        "required": ["test_id", "failure_date", "module", "device", "os_version", "severity"],
        "unique_id": None,
        "dates": ["failure_date"],
        "categories": {
            "severity": {
                "allowed": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "default": "MEDIUM"
            }
        }
    },
    "device_matrix": {
        "required": ["device_id", "device_name", "os_type", "os_version", "risk_level", "failure_rate"],
        "unique_id": "device_id",
        "numeric": {"failure_rate": {"min": 0.0, "max": 100.0, "default": 0.0}},
        "categories": {
            "os_type": {
                "allowed": ["Android", "iOS"],
                "default": "Android"
            },
            "risk_level": {
                "allowed": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "default": "LOW"
            }
        }
    },
    "code_changes": {
        "required": ["change_id", "file_path", "module", "change_type", "risk_level"],
        "unique_id": "change_id",
        # Optional system metadata columns: preserved from source when present,
        # otherwise generated at the SQLite enrichment stage.
        "optional_metadata": ["changed_at"],
        "categories": {
            "change_type": {
                "allowed": ["MODIFIED", "ADDED", "DELETED"],
                "default": "MODIFIED"
            },
            "risk_level": {
                "allowed": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
                "default": "LOW"
            }
        }
    }
}

# Column name synonyms for fuzzy/automatic mapping
SYNONYMS = {
    "test_id": ["test_id", "test id", "testid", "testcase_id", "id", "test_ids", "testids"],
    "test_name": ["test_name", "testname", "test name", "name", "title"],
    "file_path": ["file_path", "filepath", "file path", "path", "file", "files"],
    "module": ["module", "modules", "component", "components", "feature", "features"],
    "device": ["device", "devices", "device_name", "devicename", "model"],
    "os_version": ["os_version", "osversion", "os version", "version", "os", "os_type", "ostype"],
    "execution_time": ["execution_time", "executiontime", "execution time", "time", "runtime", "duration", "seconds"],
    "source_file": ["source_file", "sourcefile", "source file", "source", "from"],
    "depends_on": ["depends_on", "dependson", "depends on", "depends", "to", "dependency"],
    "failure_date": ["failure_date", "failuredate", "failure date", "date", "timestamp"],
    "severity": ["severity", "severities", "priority"],
    "device_id": ["device_id", "deviceid", "device id", "id"],
    "device_name": ["device_name", "devicename", "device name", "name"],
    "os_type": ["os_type", "ostype", "os type", "platform", "os"],
    "risk_level": ["risk_level", "risklevel", "risk level", "risk"],
    "failure_rate": ["failure_rate", "failurerate", "failure rate", "rate", "ratio"],
    "change_id": ["change_id", "changeid", "change id", "id"],
    "change_type": ["change_type", "changetype", "change type", "type", "action"],
    # System metadata field — accepted source synonyms before falling back to auto-generation
    "changed_at": [
        "changed_at", "changed at", "changedat", "changedAt",
        "change_date", "change date", "changedate",
        "modified_at", "modified at", "modifiedat", "modifiedAt",
        "updated_at", "updated at", "updatedat", "updatedAt",
    ]
}

# ---------------------------------------------------------------------------
# SYSTEM_METADATA_FIELDS
# ---------------------------------------------------------------------------
# SQLite columns that are NOT in the user-facing SCHEMAS (so the pipeline will
# never receive them from the CSV), but are declared NOT NULL in the database.
# Each entry maps  table_name -> { column: safe_default_value_or_callable }.
# A callable receives no arguments and is called once per import transaction.
# These are ONLY safe technical/system metadata fields — never business data.
# ---------------------------------------------------------------------------
SYSTEM_METADATA_FIELDS = {
    "code_changes": {
        # Timestamp of this import transaction — generated once per import batch
        "changed_at": lambda ts: ts,   # ts = import_timestamp injected at runtime
        # Boolean security flag — default False (0) when not supplied by source
        "is_security_sensitive": 0,
    },
    "test_coverage": {
        # Boolean security flag — default False (0) when not supplied by source
        "is_security_critical": 0,
    },
}


def normalize_column_name(name: str) -> str:
    """Standardize column names to lowercase snake_case for easy matching."""
    s = name.strip()
    # Replace spaces, dashes with underscores
    s = s.replace(" ", "_").replace("-", "_")
    # If no underscores and mixed case, perform camelCase split
    if "_" not in s and not s.isupper() and not s.islower():
        s = re.sub(r"(?<!^)(?=[A-Z])", "_", s)
    s = s.lower()
    s = re.sub(r"_+", "_", s)
    return s


def get_likely_match(required_col: str, uploaded_cols: List[str]) -> Optional[str]:
    """Find a likely match in uploaded columns based on synonyms or similarity."""
    req_norm = normalize_column_name(required_col)
    
    # 1. Exact normalized match
    for col in uploaded_cols:
        if normalize_column_name(col) == req_norm:
            return col
            
    # 2. Check synonyms
    syns = SYNONYMS.get(required_col, [])
    for syn in syns:
        syn_norm = normalize_column_name(syn)
        for col in uploaded_cols:
            if normalize_column_name(col) == syn_norm:
                return col
                
    # 3. Check substring matches
    for col in uploaded_cols:
        col_norm = normalize_column_name(col)
        if col_norm in req_norm or req_norm in col_norm:
            return col
            
    return None


def get_storage_paths(dataset_type: str, original_filename: str) -> Tuple[str, str]:
    """Return paths to store original raw CSV and cleaned CSV."""
    safe_name = re.sub(r"[\\/]", "", original_filename)
    if not safe_name:
        safe_name = f"{dataset_type}.csv"
        
    base, ext = os.path.splitext(safe_name)
    if not ext.lower() == ".csv":
        ext = ".csv"
        
    cleaned_name = f"{base}_cleaned{ext}"
    
    # Ensure dirs exist
    os.makedirs(os.path.join("Dataset", "Raw_Data"), exist_ok=True)
    os.makedirs(os.path.join("Dataset", "Cleaned_Data"), exist_ok=True)
    
    raw_path = os.path.join("Dataset", "Raw_Data", safe_name)
    clean_path = os.path.join("Dataset", "Cleaned_Data", cleaned_name)
    return raw_path, clean_path


def parse_and_validate_csv(
    dataset_type: str,
    file_content: bytes,
    original_filename: str,
    user_mapping: Optional[Dict[str, str]] = None,
    commit: bool = False
) -> Dict[str, Any]:
    """
    Validation + Cleaning Pipeline:
    1. Parse CSV & format checks
    2. Normalize columns & resolve mapping
    3. Analyze data quality (missing, duplicates, invalid dates/numeric/categorical)
    4. Clean data in-memory (applying rules, trimming, removing duplicates, mapping empty strings)
    5. Save raw and clean files if commit=True
    """
    report = {
        "success": True,
        "dataset_type": dataset_type,
        "filename": original_filename,
        "status": "valid",
        "total_rows_before": 0,
        "total_rows_after": 0,
        "total_cols_before": 0,
        "total_cols_after": 0,
        "columns": {
            "required": [],
            "uploaded": [],
            "valid": [],
            "missing": [],
            "extra": []
        },
        "proposed_mapping": {},
        "statistics": {
            "missing_values": 0,
            "duplicate_rows": 0,
            "duplicate_ids": 0,
            "invalid_dates": 0,
            "invalid_numeric": 0,
            "invalid_categories": 0,
            "extra_columns": 0
        },
        "before_after": {
            "rows": {"before": 0, "after": 0},
            "columns": {"before": 0, "after": 0},
            "missing": {"before": 0, "after": 0},
            "duplicates": {"before": 0, "after": 0},
            "invalid_dates": {"before": 0, "after": 0},
            "invalid_numeric": {"before": 0, "after": 0},
            "invalid_categories": {"before": 0, "after": 0}
        },
        "issues": [],
        "actions": [],
        "preview": {"before": [], "after": []},
        "is_valid_to_save": True,
        "error_message": None
    }
    
    # 0. Size check
    if len(file_content) > 5 * 1024 * 1024:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "invalid"
        report["error_message"] = "File size exceeds the 5MB limit."
        return report

    # 0.5. Empty check
    if not file_content or not file_content.strip():
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "empty"
        report["error_message"] = "Uploaded CSV file contains no data rows."
        return report

    # 1. Read CSV
    try:
        df = pd.read_csv(io.BytesIO(file_content))
    except Exception as exc:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "corrupted"
        report["error_message"] = f"Corrupted or invalid CSV format: {str(exc)}"
        return report
        
    if df.empty:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "empty"
        report["error_message"] = "Uploaded CSV file contains no data rows."
        return report

    schema = SCHEMAS.get(dataset_type)
    if not schema:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "invalid"
        report["error_message"] = f"Unknown dataset type: {dataset_type}"
        return report
        
    required_cols = schema["required"]
    uploaded_cols = list(df.columns)
    
    report["total_rows_before"] = len(df)
    report["total_cols_before"] = len(uploaded_cols)
    report["columns"]["required"] = required_cols
    report["columns"]["uploaded"] = uploaded_cols
    
    # 2. Resolve Column Mapping
    final_mapping = {}  # required_col -> uploaded_col
    missing_cols = []
    extra_cols = list(df.columns)
    
    # Track which columns we automatically matched (just for reporting)
    mapped_from_synonyms = []
    
    for req in required_cols:
        matched_col = None
        req_norm = normalize_column_name(req)
        
        # User specified mapping takes highest priority
        if user_mapping and req in user_mapping:
            user_val = user_mapping[req]
            if user_val in uploaded_cols:
                matched_col = user_val
        
        # If not user mapped, try exact normalized match only
        if not matched_col:
            for col in uploaded_cols:
                if normalize_column_name(col) == req_norm:
                    matched_col = col
                    break
                
        if matched_col:
            final_mapping[req] = matched_col
            report["columns"]["valid"].append(req)
            if matched_col in extra_cols:
                extra_cols.remove(matched_col)
        else:
            missing_cols.append(req)
            
    # Now look for mapping proposals among the missing columns
    for req in missing_cols:
        # Check synonyms
        syns = SYNONYMS.get(req, [])
        found_proposal = False
        for syn in syns:
            syn_norm = normalize_column_name(syn)
            for col in uploaded_cols:
                if col not in final_mapping.values():
                    if normalize_column_name(col) == syn_norm or normalize_column_name(col) in syn_norm or syn_norm in normalize_column_name(col):
                        report["proposed_mapping"][req] = col
                        found_proposal = True
                        break
            if found_proposal:
                break
                
        # Substring match if no synonym match
        if not found_proposal:
            req_norm = normalize_column_name(req)
            for col in uploaded_cols:
                if col not in final_mapping.values():
                    col_norm = normalize_column_name(col)
                    if col_norm in req_norm or req_norm in col_norm:
                        report["proposed_mapping"][req] = col
                        break
                        
    report["columns"]["missing"] = missing_cols
    report["columns"]["extra"] = extra_cols
    report["statistics"]["extra_columns"] = len(extra_cols)
    
    if mapped_from_synonyms:
        report["actions"].append(f"✓ Automatically normalized columns: {', '.join(mapped_from_synonyms)}")
        
    # If missing required columns, stop and request mapping
    if missing_cols:
        report["is_valid_to_save"] = False
        report["status"] = "needs_mapping"
        report["error_message"] = f"Missing required columns: {', '.join(missing_cols)}"
        # Build raw preview for display before mapping
        report["preview"]["before"] = df.head(5).fillna("").to_dict(orient="records")
        return report

    # 3. Data Quality Analysis & Cleaning (in-memory)
    clean_df = pd.DataFrame()
    for req, upload in final_mapping.items():
        clean_df[req] = df[upload]
        
    # Perform clean-up:
    # A. Trim whitespace in string columns
    trimmed_count = 0
    for col in clean_df.columns:
        if clean_df[col].dtype == object:
            # Check trimmed count
            original_strs = clean_df[col].astype(str)
            trimmed_strs = original_strs.str.strip()
            trimmed_count += (original_strs != trimmed_strs).sum()
            clean_df[col] = trimmed_strs

    if trimmed_count > 0:
        report["actions"].append(f"✓ Trimmed whitespace: {trimmed_count} cells")

    # B. Missing Value / Null normalization & detection
    # Convert "", "nan", "none", "null", "nat" to actual NaN/None
    def standardize_nulls(val):
        if pd.isna(val):
            return None
        if isinstance(val, str):
            s = val.strip()
            if s.lower() in ["", "nan", "none", "null", "nat", "undefined"]:
                return None
            return s
        return val

    for col in clean_df.columns:
        clean_df[col] = clean_df[col].apply(standardize_nulls)

    # Count missing values before filling
    missing_cells = clean_df.isna().sum().sum()
    report["statistics"]["missing_values"] = int(missing_cells)
    report["before_after"]["missing"]["before"] = int(missing_cells)

    # Fill allowed missing values
    filled_count = 0
    for col in clean_df.columns:
        null_mask = clean_df[col].isna()
        null_count = null_mask.sum()
        if null_count > 0:
            # Check dataset specific fill rules
            is_numeric = False
            fill_val = "Unknown"
            
            if "numeric" in schema and col in schema["numeric"]:
                is_numeric = True
                fill_val = schema["numeric"][col]["default"]
            
            # Enforce required identifier rule: Do NOT fabricate IDs
            if col == schema["unique_id"] or col in ["test_id", "device_id", "change_id", "source_file", "depends_on"]:
                # Report error and do not fill
                for idx in clean_df[null_mask].index:
                    report["issues"].append(f"Row {idx + 1}: Missing required identifier '{col}' (cannot import)")
                report["is_valid_to_save"] = False
            else:
                if pd.api.types.is_string_dtype(clean_df[col].dtype):
                    clean_df.loc[null_mask, col] = str(fill_val)
                else:
                    clean_df.loc[null_mask, col] = fill_val
                filled_count += int(null_count)
                report["issues"].append(f"Filled {null_count} missing values in '{col}' with '{fill_val}'")

    if filled_count > 0:
        report["actions"].append(f"✓ Filled allowed missing values: {filled_count} cells")

    # C. Date Validation
    invalid_dates_count = 0
    dropped_by_date = 0
    if "dates" in schema:
        for col in schema["dates"]:
            # Check dates
            original_dates = clean_df[col].copy()
            parsed_dates = pd.to_datetime(clean_df[col], errors='coerce')
            
            # Count invalid (where parsed is NaT but original was not Null)
            invalid_mask = parsed_dates.isna() & original_dates.notna()
            invalid_dates_count += invalid_mask.sum()
            report["statistics"]["invalid_dates"] = int(invalid_dates_count)
            report["before_after"]["invalid_dates"]["before"] = int(invalid_dates_count)
            
            # Report issues for invalid dates
            for idx in clean_df[invalid_mask].index:
                report["issues"].append(f"Row {idx + 1}: Invalid date '{original_dates.loc[idx]}' in '{col}' (row will be dropped)")
            
            # Drop rows with invalid or missing dates
            drop_mask = parsed_dates.isna()
            if drop_mask.any():
                dropped_by_date = int(drop_mask.sum())
                clean_df = clean_df[~drop_mask].reset_index(drop=True)
                report["actions"].append(f"⚠ Dropped {dropped_by_date} rows due to invalid/missing date in '{col}'")

    # D. Numeric validation
    invalid_nums_count = 0
    numeric_corrections = 0
    if "numeric" in schema:
        for col, rules in schema["numeric"].items():
            original_nums = clean_df[col].copy()
            parsed_nums = pd.to_numeric(clean_df[col], errors='coerce')
            
            # Identify invalid types (where parsed is NaN but original was not Null)
            type_invalid_mask = parsed_nums.isna() & original_nums.notna()
            invalid_nums_count += type_invalid_mask.sum()
            
            for idx in clean_df[type_invalid_mask].index:
                report["issues"].append(f"Row {idx + 1}: Non-numeric value '{original_nums.loc[idx]}' in '{col}' (reset to {rules['default']})")
                numeric_corrections += 1
            
            # Fill coerced NaNs
            clean_df[col] = parsed_nums.fillna(rules["default"])
            
            # Check bounds
            if "min" in rules:
                under_mask = clean_df[col] < rules["min"]
                under_count = under_mask.sum()
                if under_count > 0:
                    invalid_nums_count += under_count
                    for idx in clean_df[under_mask].index:
                        original_val = clean_df.loc[idx, col]
                        if col == "execution_time":
                            # For execution_time, take absolute value
                            corrected_val = abs(original_val)
                            report["issues"].append(f"Row {idx + 1}: Negative '{col}' '{original_val}' (converted to absolute value '{corrected_val}')")
                            clean_df.loc[idx, col] = corrected_val
                        else:
                            corrected_val = rules["min"]
                            report["issues"].append(f"Row {idx + 1}: Value '{original_val}' in '{col}' is below min {rules['min']} (clipped to {corrected_val})")
                            clean_df.loc[idx, col] = corrected_val
                        numeric_corrections += 1
                        
            if "max" in rules:
                over_mask = clean_df[col] > rules["max"]
                over_count = over_mask.sum()
                if over_count > 0:
                    invalid_nums_count += over_count
                    for idx in clean_df[over_mask].index:
                        original_val = clean_df.loc[idx, col]
                        corrected_val = rules["max"]
                        report["issues"].append(f"Row {idx + 1}: Value '{original_val}' in '{col}' exceeds max {rules['max']} (clipped to {corrected_val})")
                        clean_df.loc[idx, col] = corrected_val
                        numeric_corrections += 1

    report["statistics"]["invalid_numeric"] = int(invalid_nums_count)
    report["before_after"]["invalid_numeric"]["before"] = int(invalid_nums_count)
    if numeric_corrections > 0:
        report["actions"].append(f"✓ Corrected invalid numeric values: {numeric_corrections} cells")

    # E. Categorical validation
    invalid_cats_count = 0
    cat_corrections = 0
    if "categories" in schema:
        for col, cat_rules in schema["categories"].items():
            original_cats = clean_df[col].copy()
            allowed = cat_rules["allowed"]
            default_val = cat_rules["default"]
            
            # Check each cell
            for idx in clean_df.index:
                val = clean_df.loc[idx, col]
                if val is None:
                    continue
                # Harmless case normalization check
                matched_allowed = None
                for a in allowed:
                    if str(val).strip().upper() == a.upper():
                        matched_allowed = a
                        break
                
                if matched_allowed:
                    if str(val) != matched_allowed:
                        clean_df.loc[idx, col] = matched_allowed
                        cat_corrections += 1
                else:
                    # Truly invalid
                    invalid_cats_count += 1
                    report["issues"].append(f"Row {idx + 1}: Invalid category '{val}' in '{col}' (reset to '{default_val}')")
                    
                    # Try smart recovery for os_type
                    if col == "os_type":
                        v_str = str(val).lower()
                        if "ios" in v_str or "apple" in v_str:
                            clean_df.loc[idx, col] = "iOS"
                        elif "android" in v_str or "google" in v_str:
                            clean_df.loc[idx, col] = "Android"
                        else:
                            clean_df.loc[idx, col] = default_val
                    else:
                        clean_df.loc[idx, col] = default_val
                    cat_corrections += 1

    report["statistics"]["invalid_categories"] = int(invalid_cats_count)
    report["before_after"]["invalid_categories"]["before"] = int(invalid_cats_count)
    if cat_corrections > 0:
        report["actions"].append(f"✓ Standardized categorical values: {cat_corrections} cells")

    # F. Duplicate Rows check
    raw_duplicates = df.duplicated().sum()
    report["statistics"]["duplicate_rows"] = int(raw_duplicates)
    report["before_after"]["duplicates"]["before"] = int(raw_duplicates)
    
    clean_duplicates = clean_df.duplicated().sum()
    if clean_duplicates > 0:
        clean_df = clean_df.drop_duplicates().reset_index(drop=True)
        report["actions"].append(f"✓ Removed exact duplicates: {clean_duplicates} rows")
        
    # G. Duplicate IDs (unique key)
    unique_id_col = schema["unique_id"]
    if unique_id_col:
        original_ids = clean_df[unique_id_col].copy()
        dup_ids_mask = clean_df.duplicated(subset=[unique_id_col], keep=False)
        dup_ids = clean_df[dup_ids_mask][unique_id_col].unique()
        
        report["statistics"]["duplicate_ids"] = len(dup_ids)
        if len(dup_ids) > 0:
            for d_id in dup_ids:
                report["issues"].append(f"Duplicate ID detected: '{d_id}' in '{unique_id_col}' (keeping first occurrence)")
                
            # Drop duplicate IDs
            clean_df = clean_df.drop_duplicates(subset=[unique_id_col], keep="first").reset_index(drop=True)
            report["actions"].append(f"✓ Deduplicated IDs: removed {len(original_ids) - len(clean_df)} duplicate rows")

    # Final stats mapping
    report["total_rows_after"] = len(clean_df)
    report["total_cols_after"] = len(clean_df.columns)
    
    report["before_after"]["rows"]["before"] = report["total_rows_before"]
    report["before_after"]["rows"]["after"] = report["total_rows_after"]
    report["before_after"]["columns"]["before"] = report["total_cols_before"]
    report["before_after"]["columns"]["after"] = report["total_cols_after"]
    
    # 4. Compile previews
    report["preview"]["before"] = df.head(5).fillna("").to_dict(orient="records")
    report["preview"]["after"] = clean_df.head(5).fillna("").to_dict(orient="records")
    
    # 5. Save files if commit=True and is_valid_to_save=True
    if commit and report["is_valid_to_save"]:
        raw_path, clean_path = get_storage_paths(dataset_type, original_filename)
        
        # Save raw uploaded bytes
        try:
            with open(raw_path, "wb") as f:
                f.write(file_content)
            logger.info("Saved raw dataset to %s", raw_path)
        except Exception as exc:
            logger.error("Failed to save raw CSV file: %s", str(exc))
            
        # Save cleaned dataset as CSV
        try:
            clean_df.to_csv(clean_path, index=False)
            logger.info("Saved cleaned dataset to %s", clean_path)
            report["actions"].append(f"✓ Saved cleaned CSV to Dataset/Cleaned_Data/")
        except Exception as exc:
            logger.error("Failed to save cleaned CSV file: %s", str(exc))
            
    return report


def normalize_date(val) -> str:
    import pandas as pd
    from datetime import datetime
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if val_str.lower() in ["", "nan", "none", "null", "undefined", "n/a", "na"]:
        return None
    
    # Try parsing common formats
    for fmt in [
        '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%d/%m/%Y',
        '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y', '%Y%m%d'
    ]:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            continue
            
    # Try using pandas parser as a fallback
    try:
        dt = pd.to_datetime(val_str, errors='raise')
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return None

def clean_numeric(val) -> float:
    import pandas as pd
    import re
    if pd.isna(val) or val is None:
        return None
    val_str = str(val).strip()
    if val_str.lower() in ["", "nan", "none", "null", "undefined", "n/a", "na"]:
        return None
    val_str = re.sub(r'[^\d\.\-]', '', val_str)
    try:
        return float(val_str)
    except Exception:
        return None

def detect_encoding_and_delimiter(file_content: bytes):
    decoded_content = None
    detected_encoding = None
    
    # Check for UTF-16 BOM or check if it looks like UTF-16 (contains null bytes and is even length)
    has_utf16_bom = file_content.startswith(b'\xff\xfe') or file_content.startswith(b'\xfe\xff')
    looks_like_utf16 = (b'\x00' in file_content) or has_utf16_bom
    
    encodings_to_try = []
    if has_utf16_bom:
        encodings_to_try = ['utf-16']
    elif looks_like_utf16:
        encodings_to_try = ['utf-16', 'utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
    else:
        encodings_to_try = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1', 'utf-16']
        
    for enc in encodings_to_try:
        try:
            decoded = file_content.decode(enc)
            if enc == 'utf-16' and not looks_like_utf16:
                continue
            decoded_content = decoded
            detected_encoding = enc.upper()
            break
        except Exception:
            continue
            
    if not decoded_content:
        decoded_content = file_content.decode('utf-8', errors='ignore')
        detected_encoding = "UTF-8 (FALLBACK)"
        
    lines = [line.strip() for line in decoded_content.splitlines() if line.strip()]
    if not lines:
        return decoded_content, detected_encoding, ','
        
    header_line = lines[0]
    delimiters = [',', ';', '\t', '|']
    counts = {d: 0 for d in delimiters}
    in_quotes = False
    for char in header_line:
        if char == '"':
            in_quotes = not in_quotes
        elif not in_quotes and char in counts:
            counts[char] += 1
            
    detected_delimiter = ','
    max_count = -1
    for d, count in counts.items():
        if count > max_count:
            max_count = count
            detected_delimiter = d
            
    return decoded_content, detected_encoding, detected_delimiter

def parse_and_validate_full_csv(
    file_content: bytes,
    original_filename: str,
    user_mapping = None,
    commit: bool = False
):
    import io
    import csv
    import pandas as pd
    import re
    from datetime import datetime
    
    report = {
        "success": True,
        "filename": original_filename,
        "status": "READY_TO_IMPORT",
        "encoding": "UTF-8",
        "delimiter": ",",
        "total_rows": 0,
        "total_cols": 0,
        "coverage": {},
        "mapping": [],
        "repairs": [],
        "isolated_rows": [],
        "statistics": {
            "duplicate_rows": 0,
            "duplicate_ids": 0,
            "missing_values": 0,
            "invalid_numeric": 0,
            "invalid_dates": 0,
            "extra_columns": 0
        },
        "extra_columns": [],
        "missing_required_columns": {},
        "issues": [],
        "actions": [],
        "preview": {"before": [], "after": {}},
        "is_valid_to_save": True,
        "error_message": None,
        "_cleaned_dfs": {}
    }

    if len(file_content) > 5 * 1024 * 1024:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = "File size exceeds the 5MB limit."
        return report

    try:
        decoded_content, detected_encoding, detected_delimiter = detect_encoding_and_delimiter(file_content)
    except Exception as exc:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = f"Failed to decode CSV content: {str(exc)}"
        return report

    report["encoding"] = detected_encoding
    report["delimiter"] = detected_delimiter

    stream = io.StringIO(decoded_content)
    reader = csv.reader(stream, delimiter=detected_delimiter)

    try:
        raw_header = next(reader)
    except StopIteration:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = "Uploaded CSV file contains no data rows (empty header)."
        return report
    except Exception as exc:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = f"Failed to parse CSV header: {str(exc)}"
        return report

    raw_header = [h.strip() for h in raw_header]
    N = len(raw_header)
    report["total_cols"] = N

    rows = []
    repairs_log = []
    isolated_rows = []
    actions = [
        f"✓ Encoding detected: {detected_encoding}",
        f"✓ Delimiter detected: '{detected_delimiter}'",
        "✓ Header normalized"
    ]
    issues = []

    lines = [line.strip() for line in decoded_content.splitlines() if line.strip()]
    repaired_rows_count = 0
    
    for curr_line, line in enumerate(lines[1:], start=2):
        try:
            row_reader = csv.reader([line], delimiter=detected_delimiter, strict=True)
            row = next(row_reader)
        except Exception as exc:
            isolated_rows.append({
                "line": curr_line,
                "expected": N,
                "found": None,
                "reason": f"Quoting/structure error: {str(exc)}",
                "raw": line
            })
            repairs_log.append(f"Row {curr_line}: Malformed quoting. Action: Isolated.")
            continue

        M = len(row)

        if M == N:
            rows.append(row)
        elif M < N:
            missing_count = N - M
            repaired_row = row + [""] * missing_count
            rows.append(repaired_row)
            repaired_rows_count += 1
            repairs_log.append(f"Row {curr_line} repaired. Action: Added {missing_count} empty fields.")
        else:
            if all(not f.strip() for f in row[N:]):
                repaired_row = row[:N]
                rows.append(repaired_row)
                repaired_rows_count += 1
                repairs_log.append(f"Row {curr_line} repaired. Action: Truncated trailing empty fields.")
            else:
                merge_idx = None
                for idx, col_name in enumerate(raw_header):
                    col_norm = normalize_column_name(col_name)
                    if any(k in col_norm for k in ['message', 'reason', 'rationale', 'description', 'detail', 'name', 'result', 'path', 'file']):
                        merge_idx = idx
                        break
                if merge_idx is not None:
                    merged_val = detected_delimiter.join(row[merge_idx : merge_idx + (M - N) + 1])
                    repaired_row = row[:merge_idx] + [merged_val] + row[merge_idx + (M - N) + 1:]
                    repaired_row = repaired_row[:N]
                    rows.append(repaired_row)
                    repaired_rows_count += 1
                    repairs_log.append(f"Row {curr_line} repaired. Action: Merged extra fields into '{raw_header[merge_idx]}'.")
                else:
                    isolated_rows.append({
                        "line": curr_line,
                        "expected": N,
                        "found": M,
                        "reason": f"Expected {N} fields, saw {M}.",
                        "raw": line
                    })
                    repairs_log.append(f"Row {curr_line}: Inconsistent field count. Expected: {N}, Found: {M}. Action: Isolated.")

    if not rows:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = "No valid data rows remain after parsing and filtering."
        report["isolated_rows"] = isolated_rows
        report["repairs"] = repairs_log
        return report

    df = pd.DataFrame(rows, columns=raw_header)
    report["total_rows"] = len(df)
    
    if repaired_rows_count > 0:
        actions.append(f"✓ {repaired_rows_count} malformed rows repaired")
    if len(isolated_rows) > 0:
        issues.append(f"⚠ {len(isolated_rows)} unrepairable rows isolated from dataset")

    all_target_cols = set()
    for g, s in SCHEMAS.items():
        all_target_cols.update(s["required"])
        all_target_cols.update(s.get("optional_metadata", []))

    final_mapping = {}
    proposed_mapping = {}
    mapping_details = []

    for target in all_target_cols:
        matched_col = None
        match_type = "None"
        confidence = 0
        action = "NONE"
        target_norm = normalize_column_name(target)

        if user_mapping and target in user_mapping:
            user_val = user_mapping[target]
            if user_val in raw_header:
                matched_col = user_val
                match_type = "Manual"
                confidence = 100
                action = "MANUAL"

        if not matched_col:
            for col in raw_header:
                if normalize_column_name(col) == target_norm:
                    matched_col = col
                    match_type = "Exact"
                    confidence = 100
                    action = "AUTO"
                    break

        if not matched_col:
            syns = SYNONYMS.get(target, [])
            for syn in syns:
                syn_norm = normalize_column_name(syn)
                for col in raw_header:
                    if normalize_column_name(col) == syn_norm:
                        matched_col = col
                        match_type = "Synonym"
                        confidence = 95
                        action = "AUTO"
                        break
                if matched_col:
                    break

        if not matched_col:
            for col in raw_header:
                col_norm = normalize_column_name(col)
                is_relevant = False
                if target == "test_id" and ("test" in col_norm and "id" in col_norm):
                    is_relevant = True
                elif target == "test_name" and ("test" in col_norm and "name" in col_norm):
                    is_relevant = True
                elif target == "file_path" and ("file" in col_norm or "path" in col_norm):
                    is_relevant = True
                elif target == "execution_time" and ("execution" in col_norm or "runtime" in col_norm or "duration" in col_norm):
                    is_relevant = True
                elif target == "device_id" and ("device" in col_norm and "id" in col_norm):
                    is_relevant = True
                elif target == "device_name" and ("device" in col_norm and "name" in col_norm):
                    is_relevant = True
                elif target == "change_id" and ("change" in col_norm and "id" in col_norm or "commit" in col_norm):
                    is_relevant = True
                elif target == "change_type" and ("change" in col_norm and "type" in col_norm or "category" in col_norm):
                    is_relevant = True
                elif target == "failure_rate" and ("fail" in col_norm and ("rate" in col_norm or "percent" in col_norm)):
                    is_relevant = True
                elif target in ["device", "module", "severity", "os_version", "os_type", "risk_level", "source_file", "depends_on", "failure_date"]:
                    if col_norm in target_norm or target_norm in col_norm:
                        is_relevant = True

                if is_relevant:
                    matched_col = col
                    match_type = "Substring"
                    confidence = 80
                    action = "AUTO"
                    break

        if matched_col:
            final_mapping[target] = matched_col

        mapping_details.append({
            "target": target,
            "mapped_to": matched_col,
            "match_type": match_type,
            "confidence": confidence,
            "action": action
        })

    report["mapping"] = mapping_details

    total_matched = sum(1 for m in mapping_details if m["mapped_to"] is not None)
    if total_matched == 0:
        report["success"] = False
        report["is_valid_to_save"] = False
        report["status"] = "UNRECOVERABLE"
        report["error_message"] = "This dataset does not contain enough fields relevant to the TestSphere.AI data model."
        return report

    extra_columns = [col for col in raw_header if col not in final_mapping.values()]
    report["extra_columns"] = extra_columns

    identifying_cols = {
        "test_coverage": ["test_id", "test_name", "execution_time"],
        "dependency_map": ["source_file", "depends_on"],
        "failure_history": ["failure_date"],
        "device_matrix": ["device_id", "device_name", "failure_rate"],
        "code_changes": ["change_id"]
    }

    coverage = {}
    missing_required_columns = {}

    for g, schema in SCHEMAS.items():
        required = schema["required"]
        mapped = [r for r in required if r in final_mapping]
        missing = [r for r in required if r not in final_mapping]

        has_id_col = False
        for id_col in identifying_cols[g]:
            if id_col in final_mapping:
                has_id_col = True
                break

        if has_id_col:
            if len(missing) == 0:
                coverage[g] = "DETECTED"
            else:
                coverage[g] = "INCOMPLETE"
                missing_required_columns[g] = missing
        else:
            coverage[g] = "UNAVAILABLE"

    report["coverage"] = coverage
    report["missing_required_columns"] = missing_required_columns

    cleaned_data = {}
    duplicate_rows_count = 0
    duplicate_ids_count = 0
    missing_values_count = 0
    invalid_numeric_count = 0
    invalid_dates_count = 0

    for g in ["test_coverage", "dependency_map", "failure_history", "device_matrix", "code_changes"]:
        if coverage[g] != "DETECTED":
            continue

        schema = SCHEMAS[g]
        required_cols = schema["required"]

        group_df = df[[final_mapping[req] for req in required_cols]].copy()
        group_df.columns = required_cols

        # Include optional_metadata columns when they are mapped from the source.
        # These are columns like changed_at that are NOT required for schema detection
        # but SHOULD be preserved when the user supplies them.
        for opt_col in schema.get("optional_metadata", []):
            if opt_col in final_mapping and final_mapping[opt_col] in df.columns:
                group_df[opt_col] = df[final_mapping[opt_col]].values

        trimmed_count = 0
        for col in group_df.columns:
            if group_df[col].dtype == object:
                orig = group_df[col].astype(str)
                trimmed = orig.str.strip()
                trimmed_count += (orig != trimmed).sum()
                group_df[col] = trimmed
        if trimmed_count > 0:
            actions.append(f"✓ [{g}] Trimmed whitespace in {trimmed_count} cells.")

        def standardize_nulls(val):
            if pd.isna(val):
                return None
            if isinstance(val, str):
                s = val.strip()
                if s.lower() in ["", "nan", "none", "null", "nat", "undefined", "n/a", "na"]:
                    return None
                return s
            return val

        for col in group_df.columns:
            group_df[col] = group_df[col].apply(standardize_nulls)

        drop_mask = pd.Series(False, index=group_df.index)
        for col in group_df.columns:
            null_mask = group_df[col].isna()
            if null_mask.any():
                missing_values_count += int(null_mask.sum())
                if col in [schema["unique_id"], "test_id", "device_id", "change_id", "file_path", "source_file", "depends_on"]:
                    drop_mask = drop_mask | null_mask
                    null_indices = group_df[null_mask].index.tolist()
                    for idx in null_indices[:5]:
                        issues.append(f"⚠ [{g}] Row {idx + 1}: Missing critical identifier '{col}' (row will be dropped).")
                    if len(null_indices) > 5:
                        issues.append(f"⚠ [{g}] ... and {len(null_indices) - 5} more rows with missing '{col}'.")
                else:
                    fill_val = "Unknown"
                    if "numeric" in schema and col in schema["numeric"]:
                        fill_val = schema["numeric"][col]["default"]
                    elif "categories" in schema and col in schema["categories"]:
                        fill_val = schema["categories"][col]["default"]
                    
                    if pd.api.types.is_string_dtype(group_df[col].dtype):
                        group_df.loc[null_mask, col] = str(fill_val)
                    else:
                        group_df.loc[null_mask, col] = fill_val
                    actions.append(f"✓ [{g}] Filled {null_mask.sum()} missing values in '{col}' with '{fill_val}'.")

        dropped_missing = drop_mask.sum()
        if dropped_missing > 0:
            group_df = group_df[~drop_mask].reset_index(drop=True)
            actions.append(f"✓ [{g}] Dropped {dropped_missing} rows due to missing critical identifiers.")

        if "dates" in schema:
            for col in schema["dates"]:
                orig_dates = group_df[col].copy()
                parsed_dates = orig_dates.apply(normalize_date)
                
                invalid_date_mask = orig_dates.notna() & parsed_dates.isna()
                invalid_count = invalid_date_mask.sum()
                if invalid_count > 0:
                    invalid_dates_count += int(invalid_count)
                    invalid_indices = group_df[invalid_date_mask].index.tolist()
                    for idx in invalid_indices[:5]:
                        issues.append(f"⚠ [{g}] Row {idx + 1}: Invalid date format '{orig_dates.loc[idx]}' in '{col}' (needs review).")
                    group_df[col] = parsed_dates
                else:
                    group_df[col] = parsed_dates
                    actions.append(f"✓ [{g}] Normalized date format in '{col}'.")

        if "numeric" in schema:
            for col, rules in schema["numeric"].items():
                orig_nums = group_df[col].copy()
                parsed_nums = orig_nums.apply(clean_numeric)
                
                type_invalid_mask = orig_nums.notna() & parsed_nums.isna()
                type_invalid_count = type_invalid_mask.sum()
                if type_invalid_count > 0:
                    invalid_numeric_count += int(type_invalid_count)
                    invalid_indices = group_df[type_invalid_mask].index.tolist()
                    for idx in invalid_indices[:5]:
                        issues.append(f"⚠ [{g}] Row {idx + 1}: Non-numeric value '{orig_nums.loc[idx]}' in '{col}' (needs review).")
                
                parsed_nums = parsed_nums.fillna(rules["default"])
                
                for idx in group_df.index:
                    val = parsed_nums.loc[idx]
                    if val is not None:
                        is_out_of_bounds = False
                        corrected_val = val
                        if "min" in rules and val < rules["min"]:
                            is_out_of_bounds = True
                            if col == "execution_time":
                                corrected_val = abs(val)
                            else:
                                corrected_val = rules["min"]
                        if "max" in rules and val > rules["max"]:
                            is_out_of_bounds = True
                            corrected_val = rules["max"]
                            
                        if is_out_of_bounds:
                            invalid_numeric_count += 1
                            parsed_nums.loc[idx] = corrected_val
                            if col == "execution_time" and val < 0:
                                issues.append(f"⚠ [{g}] Row {idx + 1}: Negative '{col}' '{val}' (converted to absolute value '{corrected_val}').")
                            else:
                                issues.append(f"⚠ [{g}] Row {idx + 1}: Out-of-bounds numeric value '{orig_nums.loc[idx]}' in '{col}' (clipped to {corrected_val}).")
                        
                        if col == "execution_time" and corrected_val > 300.0:
                            issues.append(f"⚠ [{g}] Row {idx + 1}: Legitimate outlier warning: execution_time is unusually high ('{corrected_val}' s).")
                
                group_df[col] = parsed_nums

        if "categories" in schema:
            for col, cat_rules in schema["categories"].items():
                allowed = cat_rules["allowed"]
                default_val = cat_rules["default"]

                for idx in group_df.index:
                    val = group_df.loc[idx, col]
                    if val is None:
                        continue
                    matched_allowed = None
                    for a in allowed:
                        if str(val).strip().upper() == a.upper():
                            matched_allowed = a
                            break
                    if matched_allowed:
                        if str(val) != matched_allowed:
                            group_df.loc[idx, col] = matched_allowed
                    else:
                        if col == "os_type":
                            v_str = str(val).lower()
                            if "ios" in v_str or "apple" in v_str:
                                group_df.loc[idx, col] = "iOS"
                            elif "android" in v_str or "google" in v_str:
                                group_df.loc[idx, col] = "Android"
                            else:
                                group_df.loc[idx, col] = default_val
                                issues.append(f"⚠ [{g}] Row {idx + 1}: Normalized invalid category '{val}' in '{col}' to default '{default_val}'.")
                        else:
                            group_df.loc[idx, col] = default_val
                            issues.append(f"⚠ [{g}] Row {idx + 1}: Normalized invalid category '{val}' in '{col}' to default '{default_val}'.")

        dup_rows = group_df.duplicated().sum()
        if dup_rows > 0:
            group_df = group_df.drop_duplicates().reset_index(drop=True)
            duplicate_rows_count += int(dup_rows)
            actions.append(f"✓ [{g}] Removed {dup_rows} exact duplicate rows.")

        if schema["unique_id"]:
            uniq_id = schema["unique_id"]
            dup_ids = group_df.duplicated(subset=[uniq_id]).sum()
            if dup_ids > 0:
                group_df = group_df.drop_duplicates(subset=[uniq_id], keep="first").reset_index(drop=True)
                duplicate_ids_count += int(dup_ids)
                actions.append(f"✓ [{g}] Removed {dup_ids} duplicate IDs (kept first).")

        cleaned_data[g] = group_df

    report["statistics"] = {
        "duplicate_rows": duplicate_rows_count,
        "duplicate_ids": duplicate_ids_count,
        "missing_values": missing_values_count,
        "invalid_numeric": invalid_numeric_count,
        "invalid_dates": invalid_dates_count,
        "extra_columns": len(extra_columns)
    }
    report["issues"] = issues
    report["actions"] = actions
    report["isolated_rows"] = isolated_rows
    report["repairs"] = repairs_log
    report["_cleaned_dfs"] = cleaned_data

    report["preview"]["before"] = df.head(5).fillna("").to_dict(orient="records")
    report["preview"]["after"] = { g: cleaned_df.head(5).fillna("").to_dict(orient="records") for g, cleaned_df in cleaned_data.items() }

    has_detected = any(c == "DETECTED" for c in coverage.values())
    has_incomplete = any(c == "INCOMPLETE" for c in coverage.values())
    has_low_confidence = any(m["confidence"] < 90 and m["mapped_to"] is not None for m in mapping_details)
    has_invalid_values = (invalid_numeric_count > 0 or invalid_dates_count > 0)
    has_isolated = (len(isolated_rows) > 0)

    if not has_detected and not has_incomplete:
        report["status"] = "UNRECOVERABLE"
        report["is_valid_to_save"] = False
        report["error_message"] = "This dataset does not contain enough fields relevant to the TestSphere.AI data model."
    elif has_incomplete or has_low_confidence:
        report["status"] = "NEEDS_REVIEW"
        report["is_valid_to_save"] = False
        report["error_message"] = "The dataset requires column mapping review."
    else:
        has_unavailable = any(c == "UNAVAILABLE" for c in coverage.values())
        if has_unavailable:
            report["status"] = "PARTIALLY_USABLE"
            report["is_valid_to_save"] = True
        else:
            report["status"] = "READY_TO_IMPORT"
            report["is_valid_to_save"] = True

    if commit and report["is_valid_to_save"]:
        import os
        os.makedirs(os.path.join("Dataset", "Raw_Data"), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # canonical import timestamp
        raw_filename = f"raw_archive_{timestamp}_{original_filename}"
        raw_path = os.path.join("Dataset", "Raw_Data", raw_filename)
        try:
            with open(raw_path, "wb") as f:
                f.write(file_content)
            logger.info("Saved raw archive to %s", raw_path)
        except Exception as exc:
            logger.error("Failed to save raw CSV file: %s", str(exc))

        os.makedirs(os.path.join("Dataset", "Cleaned_Data"), exist_ok=True)

        # --- Pre-import SQLite schema enrichment ---
        # Inspect runtime SQLite schema, fill system metadata fields, then validate.
        enrich_errors = []
        for g, cleaned_df in cleaned_data.items():
            enriched_df, errs = _enrich_for_sqlite(g, cleaned_df, import_ts)
            if errs:
                enrich_errors.extend([f"[{g}] {e}" for e in errs])
            else:
                cleaned_data[g] = enriched_df

        if enrich_errors:
            report["success"] = False
            report["is_valid_to_save"] = False
            report["status"] = "NEEDS_REVIEW"
            report["stage"] = "DATABASE_VALIDATION"
            report["error_message"] = (
                "Dataset could not be imported because required database fields "
                "could not be safely resolved."
            )
            report["issues"] = report.get("issues", []) + enrich_errors
            report["final_mapping"] = final_mapping
            report["proposed_mapping"] = proposed_mapping
            return report

        for g, cleaned_df in cleaned_data.items():
            clean_path = os.path.join("Dataset", "Cleaned_Data", f"{g}_cleaned.csv")
            try:
                cleaned_df.to_csv(clean_path, index=False)
                logger.info("Saved cleaned dataset for %s to %s", g, clean_path)
            except Exception as exc:
                logger.error("Failed to save cleaned CSV for %s: %s", g, str(exc))

    report["final_mapping"] = final_mapping
    report["proposed_mapping"] = proposed_mapping
    return report


# ---------------------------------------------------------------------------
# Runtime SQLite schema inspection
# ---------------------------------------------------------------------------

def _inspect_sqlite_schema(table_name: str) -> list:
    """
    Read PRAGMA table_info for *table_name* from the live SQLite database.
    Returns a list of dicts with keys: name, type, notnull, dflt_value, pk.
    Returns [] if the table does not exist or the DB is unavailable.
    """
    try:
        from Engine.database import get_connection
        conn = get_connection()
        try:
            rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Could not inspect SQLite schema for %s: %s", table_name, exc)
        return []


# Known system-generated timestamp fields (TEXT NOT NULL, safe to auto-fill).
_SYSTEM_TIMESTAMP_FIELDS = {"changed_at", "created_at", "updated_at", "modified_at"}
# Known system-generated boolean integer flags (INTEGER NOT NULL, safe to default 0).
_SYSTEM_BOOL_FLAGS = {"is_security_sensitive", "is_security_critical", "is_flagged"}


def _enrich_for_sqlite(table_name: str, df: pd.DataFrame, import_ts: str):
    """
    Inspect the live SQLite schema for *table_name* and:
      1. Fill any NOT NULL columns absent from *df* if they are safe system
         metadata (timestamp flags, boolean flags).
      2. Validate that every remaining NOT NULL column has no NULL values.

    Returns (enriched_df, errors).  *errors* is an empty list on success.
    """
    schema_rows = _inspect_sqlite_schema(table_name)
    if not schema_rows:
        # Can't verify — pass through and let SQLite raise if needed.
        return df, []

    df = df.copy()
    errors = []
    mapping_notes = []  # for logging

    for col_info in schema_rows:
        col = col_info["name"]
        notnull = bool(col_info["notnull"])
        dflt = col_info["dflt_value"]
        is_pk = bool(col_info["pk"])

        # Skip the auto-increment PK — pandas/SQLite handles it.
        if is_pk:
            continue

        if col in df.columns:
            # Column present — just ensure NOT NULL rows aren't NULL.
            if notnull and df[col].isnull().any():
                null_count = int(df[col].isnull().sum())
                # For system timestamp fields, fill missing cells rather than error.
                if col in _SYSTEM_TIMESTAMP_FIELDS:
                    df[col] = df[col].fillna(import_ts)
                    mapping_notes.append(
                        f"Filled {null_count} NULL value(s) in '{col}' with import timestamp."
                    )
                elif col in _SYSTEM_BOOL_FLAGS:
                    df[col] = df[col].fillna(0)
                    mapping_notes.append(
                        f"Filled {null_count} NULL value(s) in '{col}' with default 0."
                    )
                elif dflt is not None:
                    # SQLite has a default — strip surrounding quotes.
                    safe_default = dflt.strip("'")
                    df[col] = df[col].fillna(safe_default)
                    mapping_notes.append(
                        f"Filled {null_count} NULL value(s) in '{col}' with schema default '{safe_default}'."
                    )
                else:
                    errors.append(
                        f"Column '{col}' is NOT NULL in the database but contains "
                        f"{null_count} NULL value(s) that cannot be safely resolved."
                    )
        else:
            # Column absent from dataframe.
            if not notnull:
                # Nullable — SQLite will use its default or NULL; no action needed.
                continue

            # NOT NULL and absent — attempt safe auto-fill.
            if col in _SYSTEM_TIMESTAMP_FIELDS:
                df[col] = import_ts
                mapping_notes.append(
                    f"Column '{col}' not in source data — generated system import timestamp."
                )
            elif col in _SYSTEM_BOOL_FLAGS:
                df[col] = 0
                mapping_notes.append(
                    f"Column '{col}' not in source data — defaulted to 0 (system flag)."
                )
            elif dflt is not None:
                safe_default = dflt.strip("'")
                df[col] = safe_default
                mapping_notes.append(
                    f"Column '{col}' not in source data — applied schema default '{safe_default}'."
                )
            else:
                errors.append(
                    f"Column '{col}' is NOT NULL in the database with no safe default "
                    f"and was not present in the source dataset."
                )

    for note in mapping_notes:
        logger.info("[%s] SQLite enrichment: %s", table_name, note)

    return df, errors
