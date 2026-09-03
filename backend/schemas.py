"""
TestSphere AI — Pydantic Schemas
Defines input/output payloads for API routes.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict


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
    understandable: int
    clear_reasons: int
    trust_system: int
    rollback_useful: int
    dashboard_clear: int
    additional_comments: Optional[str] = None
    rating: int = 5

