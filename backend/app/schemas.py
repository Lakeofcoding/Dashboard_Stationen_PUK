"""
Pydantic-Modelle fuer API Requests und Responses.
Zentral gesammelt damit Router und Services sie importieren koennen.
"""
from __future__ import annotations
from datetime import date
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

Severity = Literal["OK", "WARN", "CRITICAL"]


class Alert(BaseModel):
    rule_id: str
    severity: Severity
    category: Literal["completeness", "medical"] = "medical"
    message: str
    explanation: str
    condition_hash: str


# --- Kompakte Parameter-Statusleiste pro Fall ---
class ParameterStatus(BaseModel):
    """Status eines einzelnen Parameters: OK, WARN, CRITICAL oder N/A."""
    id: str              # z.B. "honos_entry", "ekg", "clozapin"
    label: str           # Kurzname fuer Anzeige
    group: Literal["completeness", "medical"]
    status: Literal["ok", "warn", "critical", "na"]  # na = nicht relevant
    detail: Optional[str] = None  # Erklaerungstext


class CaseSummary(BaseModel):
    case_id: str
    patient_id: str
    clinic: str
    center: str
    station_id: str
    admission_date: date
    discharge_date: Optional[date] = None
    severity: Severity
    top_alert: Optional[str] = None
    critical_count: int = 0
    warn_count: int = 0
    acked_at: Optional[str] = None
    parameter_status: list[ParameterStatus] = Field(default_factory=list)


class CaseDetail(CaseSummary):
    honos: Optional[int] = None
    bscl: Optional[int] = None
    bfs_complete: bool = False
    alerts: list[Alert] = Field(default_factory=list)
    rule_states: dict[str, dict[str, Any]] = Field(default_factory=dict)


# --- ACK / Shift ---
class AckRequest(BaseModel):
    case_id: str
    rule_id: Optional[str] = None
    scope: Literal["case", "rule"] = "rule"
    shift_code: Optional[str] = None
    reason: Optional[str] = None


# --- Day State ---
class DayStateResponse(BaseModel):
    station_id: str
    business_date: str
    version: int


# --- Admin models ---
class AdminUserRoleAssignment(BaseModel):
    role_id: str
    station_id: str = "*"

class AdminUserCreate(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    is_active: bool = True
    roles: Optional[list[AdminUserRoleAssignment]] = None

class AdminUserUpdate(BaseModel):
    display_name: Optional[str] = None
    is_active: Optional[bool] = None

class AdminAssignRole(BaseModel):
    role_id: str
    station_id: str = "*"

class AdminPermissionCreate(BaseModel):
    perm_id: str
    description: Optional[str] = None

class AdminPermissionUpdate(BaseModel):
    description: Optional[str] = None

class AdminRoleCreate(BaseModel):
    role_id: str
    description: Optional[str] = None

class AdminRoleUpdate(BaseModel):
    description: Optional[str] = None

class AdminRolePermissions(BaseModel):
    permissions: list[str]

class AdminRuleUpsert(BaseModel):
    rule_id: str
    display_name: Optional[str] = None
    message: Optional[str] = None
    explanation: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    value: Any = None
    enabled: Optional[bool] = None

class BreakGlassActivateReq(BaseModel):
    reason: str
    station_scope: str = "*"
    duration_minutes: int = 60

class BreakGlassRevokeReq(BaseModel):
    review_note: str = ""

class ShiftReasonCreate(BaseModel):
    code: str
    label: str
    description: Optional[str] = None
    sort_order: int = 99

class ShiftReasonUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

class StationOverviewItem(BaseModel):
    station_id: str
    center: str
    total_cases: int = 0
    open_cases: int = 0
    critical_count: int = 0
    warn_count: int = 0
    ok_count: int = 0
    severity: Severity = "OK"

class NotificationRuleCreate(BaseModel):
    name: str
    email: str
    station_id: Optional[str] = None
    min_severity: str = "WARN"
    category: Optional[str] = None
    delay_minutes: int = 0
    is_active: bool = True

class NotificationRuleUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    station_id: Optional[str] = None
    min_severity: Optional[str] = None
    category: Optional[str] = None
    delay_minutes: Optional[int] = None
    is_active: Optional[bool] = None
