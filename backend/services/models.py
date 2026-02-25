"""
Datei: backend/services/models.py

Zweck:
- Pydantic Models für Services
- Request/Response Schemas
- Data Transfer Objects (DTOs)

Zentrale Models für API-Kommunikation.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# =============================================================================
# Case Models
# =============================================================================

Severity = Literal["OK", "WARN", "CRITICAL"]
ShiftCode = Literal["a", "b", "c"]


class Alert(BaseModel):
    """Alert-Modell für Frontend."""
    rule_id: str
    severity: Severity
    category: Literal["completeness", "medical"] = "medical"
    message: str
    explanation: str
    condition_hash: str
    acked: bool = False
    shifted: bool = False
    shift_code: Optional[str] = None


class CaseSummary(BaseModel):
    """Case-Übersicht für Listen-Ansicht."""
    case_id: str
    station_id: str
    admission_date: date
    discharge_date: Optional[date] = None
    worst_severity: Severity
    alert_count: int
    all_acked: bool
    alerts: list[Alert]


class CaseDetail(BaseModel):
    """Detaillierte Case-Informationen."""
    case_id: str
    station_id: str
    admission_date: date
    discharge_date: Optional[date] = None
    
    # Scores
    honos_entry_total: Optional[int] = None
    honos_discharge_total: Optional[int] = None
    bscl_total_entry: Optional[float] = None
    bscl_total_discharge: Optional[float] = None
    
    # BFS
    bfs_1: Optional[str] = None
    bfs_2: Optional[str] = None
    bfs_3: Optional[str] = None
    
    # Vollständigkeit
    completeness_scores: dict[str, Any]
    
    # Alerts
    alerts: list[Alert]
    worst_severity: Severity


class AckRequest(BaseModel):
    """Request für Acknowledge-Operation."""
    case_id: str
    rule_id: str
    condition_hash: str
    comment: Optional[str] = None


class ShiftRequest(BaseModel):
    """Request für Shift-Operation."""
    case_id: str
    rule_id: str
    condition_hash: str
    shift_code: ShiftCode
    comment: Optional[str] = None


# =============================================================================
# Admin Models
# =============================================================================

class UserResponse(BaseModel):
    """User-Response für Admin-API."""
    user_id: str
    display_name: Optional[str] = None
    is_active: bool
    created_at: str
    roles: list[str] = []


class CreateUserRequest(BaseModel):
    """Request zum Erstellen eines Users."""
    user_id: str
    display_name: Optional[str] = None
    is_active: bool = True


class UpdateUserRequest(BaseModel):
    """Request zum Aktualisieren eines Users."""
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    """Role-Response für Admin-API."""
    role_id: str
    description: Optional[str] = None
    is_system: bool
    permissions: list[str] = []


class CreateRoleRequest(BaseModel):
    """Request zum Erstellen einer Rolle."""
    role_id: str
    description: Optional[str] = None
    permissions: list[str] = []


class UpdateRoleRequest(BaseModel):
    """Request zum Aktualisieren einer Rolle."""
    description: Optional[str] = None
    permissions: Optional[list[str]] = None


class RuleDefinitionResponse(BaseModel):
    """Rule-Definition Response."""
    rule_id: str
    display_name: Optional[str] = None
    message: str
    explanation: str
    category: str
    severity: str
    metric: str
    operator: str
    value_json: str
    enabled: bool
    is_system: bool
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


class UpdateRuleRequest(BaseModel):
    """Request zum Aktualisieren einer Regel."""
    display_name: Optional[str] = None
    message: Optional[str] = None
    explanation: Optional[str] = None
    enabled: Optional[bool] = None


class AuditEventResponse(BaseModel):
    """Audit-Event Response."""
    event_id: str
    ts: str
    case_id: str
    station_id: str
    event_type: str
    user_id: Optional[str] = None
    payload: Optional[str] = None


class BreakGlassSessionResponse(BaseModel):
    """Break-Glass-Session Response."""
    session_id: str
    user_id: str
    station_id: str
    reason: str
    created_at: str
    expires_at: str
    revoked_at: Optional[str] = None
    revoked_by: Optional[str] = None
    review_note: Optional[str] = None
