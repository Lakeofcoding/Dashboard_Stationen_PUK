"""
Pydantic-Modelle fuer API Requests und Responses.
Zentral gesammelt damit Router und Services sie importieren koennen.
"""
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
    # Alert-Mapping (v5): verknüpft Parameter mit Regel für ACK/SHIFT
    rule_id: Optional[str] = None          # z.B. "SPIGES_ZIVILSTAND_MISSING"
    explanation: Optional[str] = None      # Langtext der Regel
    condition_hash: Optional[str] = None   # Hash für Re-Fire-Erkennung
    # ACK/SHIFT Status (vom Router injiziert)
    ack: Optional[dict] = None             # {"state": "ACK"|"SHIFT", "ts": "...", "shift_code": "a"|null}


class ParameterGroup(BaseModel):
    """Hierarchische Gruppe mit worst-child Severity-Kaskade."""
    key: str             # z.B. "spiges_person", "fu", "honos"
    label: str           # Anzeigename
    severity: Severity   # worst-child: CRITICAL > WARN > OK
    # items als dict statt ParameterStatus — verhindert dass Pydantic
    # dynamisch gesetzte Felder (rule_id, explanation, ack) verliert
    items: list[dict] = Field(default_factory=list)


class LangliegerStatus(BaseModel):
    """Top-Level Langlieger-Warnung (nicht in Parametergruppen)."""
    active: bool = False
    severity: Severity = "OK"
    days: int = 0
    week: Optional[int] = None            # Aktuelle Woche (4, 6, 8, 10...)
    message: Optional[str] = None
    next_threshold: Optional[int] = None  # Nächste Schwelle in Tagen


class FuStatus(BaseModel):
    """FU-Zusammenfassung mit Ablauf-Countdown."""
    is_fu: bool = False
    fu_typ: Optional[str] = None          # "aerztlich" | "kesb"
    fu_datum: Optional[str] = None
    fu_gueltig_bis: Optional[str] = None
    days_until_expiry: Optional[int] = None
    severity: Severity = "OK"
    message: Optional[str] = None


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
    # Severity pro Kategorie (fuer gefilterte Ansicht)
    completeness_severity: Severity = "OK"
    completeness_critical: int = 0
    completeness_warn: int = 0
    medical_severity: Severity = "OK"
    medical_critical: int = 0
    medical_warn: int = 0
    # Fallstatus & Verantwortlichkeit
    case_status: Optional[str] = None
    responsible_person: Optional[str] = None
    acked_at: Optional[str] = None
    parameter_status: list[ParameterStatus] = Field(default_factory=list)
    # Neu (v4): Aufenthaltsdauer + Langlieger
    days_since_admission: int = 0
    langlieger: Optional[LangliegerStatus] = None


class CaseDetail(CaseSummary):
    honos: Optional[int] = None
    bscl: Optional[float] = None  # BSCL Durchschnittswert (0.0–4.0)
    bfs_complete: bool = False
    alerts: list[Alert] = Field(default_factory=list)
    rule_states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # Neu (v4): Parametergruppen + FU
    parameter_groups: list[ParameterGroup] = Field(default_factory=list)
    fu_status: Optional[FuStatus] = None


# --- ACK / Shift ---
class AckRequest(BaseModel):
    case_id: str
    ack_scope: Literal["case", "rule"] = "rule"
    scope_id: str = "*"
    action: Literal["ACK", "SHIFT"] = "ACK"
    shift_code: Optional[str] = None
    comment: Optional[str] = None  # optionaler Freitext (= DB Ack.comment)


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
    clinic: str = "UNKNOWN"
    total_cases: int = 0
    open_cases: int = 0
    critical_count: int = 0
    warn_count: int = 0
    ok_count: int = 0
    severity: Severity = "OK"
    # Per-category
    completeness_critical: int = 0
    completeness_warn: int = 0
    completeness_severity: Severity = "OK"
    medical_critical: int = 0
    medical_warn: int = 0
    medical_severity: Severity = "OK"

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
