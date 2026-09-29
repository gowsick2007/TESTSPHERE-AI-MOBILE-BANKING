"""
TestSphere AI — Pydantic Schemas
Defines input/output payloads for API routes.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class LoginRequest(BaseModel):
    username: str = Field(..., description="Login username")
    password: str = Field(..., description="Login password")


class LoginResponse(BaseModel):
    success: bool
    username: str
    role: str
    token: Optional[str] = None
    error: Optional[str] = None


class ChangeAnalysisRequest(BaseModel):
    changed_files: List[str] = Field(..., description="List of modified file paths")
    change_type: str = Field("MODIFIED", description="Type of change: ADDED, MODIFIED, DELETED")
    module: Optional[str] = Field(None, description="Primary module changed")
    is_security_sensitive: bool = Field(False, description="Flag for security critical changes")
    risk_level: str = Field("MEDIUM", description="Change risk assessment: LOW, MEDIUM, HIGH, CRITICAL")


class WhatIfRequest(BaseModel):
    module: str
    device: str
    change_type: str = "MODIFIED"
    risk_level: str = "MEDIUM"
    is_security_sensitive: bool = False


class RollbackRequest(BaseModel):
    to_strategy: str = Field(..., description="Target strategy (LEGACY_FULL_SUITE or SMART_SELECTOR)")
    reason: str = Field(..., description="Reason/context for triggering switch")
    changed_by: Optional[str] = Field(None, description="Authorized username executing rollback")


class FeedbackRequest(BaseModel):
    understandable: Optional[int] = 5
    clear_reasons: Optional[int] = 5
    trust_system: Optional[int] = 5
    rollback_useful: Optional[int] = 5
    dashboard_clear: Optional[int] = 5
    additional_comments: Optional[str] = None
    rating: int = 5
    reviewer_name: Optional[str] = None
    project_area: Optional[str] = "General"
    comments: Optional[str] = None
    linked_entity_id: Optional[str] = None


class ExecutionPlanRequest(BaseModel):
    changed_files: List[str]
    change_type: str = "MODIFIED"
    module: Optional[str] = None
    is_security_sensitive: bool = False
    risk_level: str = "MEDIUM"
    strategy: str = "SMART_SELECTOR"
    change_id: Optional[str] = None


class ExecutePlanRequest(BaseModel):
    plan_id: str
    execution_type: str = "SIMULATED"
    experiment_id: Optional[str] = None


class ExperimentCreateRequest(BaseModel):
    scenario: str
    changed_files: List[str]
    module: Optional[str] = None
    is_security_sensitive: bool = False
    risk_level: str = "MEDIUM"
    threshold: float = 50.0
    seed: int = 12345


class ExperimentCompareRequest(BaseModel):
    experiment_ids: List[str]


class StrategyVersionCreateRequest(BaseModel):
    version_id: str
    strategy_name: str
    threshold: float = 50.0
    scoring_weights: Dict[str, Any]
    safety_rules: List[str]
    description: Optional[str] = None


class DecisionRecord(BaseModel):
    test_id: str
    test_name: str
    module: Optional[str] = "Unknown"
    device: Optional[str] = "Unknown"
    os_version: Optional[str] = "—"
    execution_time: Optional[float] = 0.5
    risk_score: int
    decision: str
    confidence: str
    evidence: List[str] = []
    overrides: List[Any] = []
    rationale: str
    why_run: Optional[List[str]] = None
    why_skip: Optional[List[str]] = None


class SelectionResponse(BaseModel):
    change_context: Dict[str, Any]
    dependency_info: Dict[str, Any]
    coverage_info: Dict[str, Any]
    failure_info: Dict[str, Any]
    decisions: List[Dict[str, Any]]
    summary: Dict[str, Any]



