"""
Datei: backend/routers/cases.py

Zweck:
- Case-Management Endpoints
- Case-Listing, Details, Acknowledge, Shift

Router für alle case-bezogenen Operationen.
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import AuthContext, require_ctx
from app.rbac import require_permission
from services.case_service import CaseService
from services.models import CaseSummary, CaseDetail, AckRequest, ShiftRequest

router = APIRouter(prefix="/api", tags=["cases"])


@router.get("/cases", response_model=List[CaseSummary])
def list_cases(
    ctx: AuthContext = Depends(require_ctx),
    show_all: bool = Query(False, description="Alle Fälle anzeigen (inkl. quittierte)"),
) -> List[CaseSummary]:
    """
    Listet alle Fälle für die aktuelle Station.
    
    - Filtert nach Station-ID aus Context
    - Optional: zeige auch quittierte Fälle
    - Sortiert nach Severity (CRITICAL > WARN > OK)
    """
    require_permission(ctx, "dashboard:view")
    
    case_service = CaseService()
    return case_service.list_cases(
        station_id=ctx.station_id,
        show_all=show_all
    )


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case_detail(
    case_id: str,
    ctx: AuthContext = Depends(require_ctx),
) -> CaseDetail:
    """
    Liefert Details zu einem spezifischen Fall.
    
    - Validiert Zugriff auf Station
    - Gibt alle Alerts und Scores zurück
    """
    require_permission(ctx, "dashboard:view")
    
    case_service = CaseService()
    detail = case_service.get_case_detail(
        case_id=case_id,
        station_id=ctx.station_id
    )
    
    if not detail:
        raise HTTPException(status_code=404, detail="Case nicht gefunden")
    
    return detail


@router.post("/ack")
def acknowledge_alert(
    req: AckRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """
    Quittiert eine Meldung für heute.
    
    - Erfordert Permission "dashboard:ack"
    - Speichert ACK mit Business-Date und Version
    - Audit-Log
    """
    require_permission(ctx, "dashboard:ack")
    
    case_service = CaseService()
    result = case_service.acknowledge(
        request=req,
        user_id=ctx.user_id,
        station_id=ctx.station_id
    )
    
    return result


@router.post("/shift")
def shift_alert(
    req: ShiftRequest,
    ctx: AuthContext = Depends(require_ctx),
):
    """
    Schiebt eine Meldung (a/b/c) für heute.
    
    - Erfordert Permission "dashboard:ack"
    - Speichert SHIFT mit Code und Business-Date
    - Audit-Log
    """
    require_permission(ctx, "dashboard:ack")
    
    case_service = CaseService()
    result = case_service.shift(
        request=req,
        user_id=ctx.user_id,
        station_id=ctx.station_id
    )
    
    return result


@router.post("/reset")
def reset_day(
    ctx: AuthContext = Depends(require_ctx),
):
    """
    Setzt den Geschäftstag zurück.
    
    - Erfordert Permission "dashboard:reset"
    - Inkrementiert Tagesversion
    - Invalidiert alle heutigen ACKs/Shifts
    - Audit-Log
    """
    require_permission(ctx, "dashboard:reset")
    
    case_service = CaseService()
    result = case_service.reset_day(
        station_id=ctx.station_id,
        user_id=ctx.user_id
    )
    
    return result
