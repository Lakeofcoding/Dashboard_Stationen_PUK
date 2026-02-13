from __future__ import annotations

"""Persistenz für Quittierungen (ACK) und "Schieben" (SHIFT).

Dieses Modul kapselt alle Datenbank-Schreibzugriffe.

Design-Idee:
  - `Ack` ist der *aktuelle Zustand* (Upsert auf einem festen Key).
  - `AckEvent` ist ein *Audit-Log* (append-only), um nachvollziehen zu können,
    wer wann was gemacht hat.

Zusätzlich speichern wir pro Ack den Geschäftstag und eine Tagesversion
("Vers"). Bei einem Reset wird die Version erhöht; alte Acks werden dadurch
automatisch ungültig.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Ack, AckEvent


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AckStore:
    """
    Writes:
      - ack: current state (upsert)
      - ack_event: append-only audit trail
    Reads:
      - bulk reads for station dashboard
      - audit events for debugging/admin
    """

    def _insert_event(
        self,
        *,
        case_id: str,
        station_id: str,
        ack_scope: str,
        scope_id: str,
        event_type: str,
        user_id: str | None,
        payload: dict[str, Any] | None = None,
    ) -> AckEvent:
        return AckEvent(
            event_id=str(uuid.uuid4()),
            ts=_now_iso(),
            case_id=case_id,
            station_id=station_id,
            ack_scope=ack_scope,
            scope_id=scope_id,
            event_type=event_type,
            user_id=user_id,
            payload=json.dumps(payload, ensure_ascii=False) if payload is not None else None,
        )

    def upsert_ack(
        self,
        *,
        case_id: str,
        station_id: str,
        ack_scope: str,
        scope_id: str,
        user_id: str,
        comment: str | None = None,
        condition_hash: str | None = None,
        business_date: str | None = None,
        version: int | None = None,
        action: str | None = None,
        shift_code: str | None = None,
    ) -> Ack:
        now = _now_iso()

        with SessionLocal() as db:
            existing = db.get(Ack, (case_id, station_id, ack_scope, scope_id))

            if existing:
                old = {
                    "acked_at": existing.acked_at,
                    "acked_by": existing.acked_by,
                    "comment": existing.comment,
                    "condition_hash": getattr(existing, "condition_hash", None),
                    "business_date": getattr(existing, "business_date", None),
                    "version": getattr(existing, "version", None),
                    "action": getattr(existing, "action", None),
                    "shift_code": getattr(existing, "shift_code", None),
                }

                existing.acked_at = now
                existing.acked_by = user_id
                existing.comment = comment
                existing.condition_hash = condition_hash
                existing.business_date = business_date
                existing.version = version
                existing.action = action
                existing.shift_code = shift_code

                db.add(
                    self._insert_event(
                        case_id=case_id,
                        station_id=station_id,
                        ack_scope=ack_scope,
                        scope_id=scope_id,
                        event_type="ACK_UPDATE" if (action or "ACK") == "ACK" else "SHIFT_UPDATE",
                        user_id=user_id,
                        payload={
                            "old": old,
                            "new": {
                                "acked_at": now,
                                "acked_by": user_id,
                                "comment": comment,
                                "condition_hash": condition_hash,
                                "business_date": business_date,
                                "version": version,
                                "action": action,
                                "shift_code": shift_code,
                            },
                        },
                    )
                )

                db.commit()
                db.refresh(existing)
                return existing

            row = Ack(
                case_id=case_id,
                station_id=station_id,
                ack_scope=ack_scope,
                scope_id=scope_id,
                acked_at=now,
                acked_by=user_id,
                comment=comment,
                condition_hash=condition_hash,
                business_date=business_date,
                version=version,
                action=action,
                shift_code=shift_code,
            )
            db.add(row)

            db.add(
                self._insert_event(
                    case_id=case_id,
                    station_id=station_id,
                    ack_scope=ack_scope,
                    scope_id=scope_id,
                    event_type="ACK" if (action or "ACK") == "ACK" else "SHIFT",
                    user_id=user_id,
                    payload={
                        "acked_at": now,
                        "acked_by": user_id,
                        "comment": comment,
                        "condition_hash": condition_hash,
                        "business_date": business_date,
                        "version": version,
                        "action": action,
                        "shift_code": shift_code,
                    },
                )
            )

            db.commit()
            db.refresh(row)
            return row

    def invalidate_rule_ack_if_mismatch(
        self,
        *,
        case_id: str,
        station_id: str,
        rule_id: str,
        current_hash: str,
    ) -> bool:
        """
        If a rule-ack exists but its stored condition_hash differs from the current hash,
        delete the ack_state and write a single AUTO_REOPEN event. Returns True if invalidated.
        """
        with SessionLocal() as db:
            ack = db.get(Ack, (case_id, station_id, "rule", rule_id))
            if not ack:
                return False

            old_hash = getattr(ack, "condition_hash", None)
            if old_hash == current_hash:
                return False

            db.delete(ack)

            db.add(
                self._insert_event(
                    case_id=case_id,
                    station_id=station_id,
                    ack_scope="rule",
                    scope_id=rule_id,
                    event_type="AUTO_REOPEN",
                    user_id=None,
                    payload={
                        "old_condition_hash": old_hash,
                        "new_condition_hash": current_hash,
                    },
                )
            )

            db.commit()
            return True

    def get_acks_for_cases(self, case_ids: list[str], station_id: str) -> list[Ack]:
        if not case_ids:
            return []

        with SessionLocal() as db:
            stmt = select(Ack).where(
                Ack.station_id == station_id,
                Ack.case_id.in_(case_ids),
            )
            return list(db.execute(stmt).scalars().all())

    def list_events(
        self,
        *,
        station_id: str,
        case_id: str | None = None,
        limit: int = 200,
    ) -> list[AckEvent]:
        with SessionLocal() as db:
            stmt = select(AckEvent).where(AckEvent.station_id == station_id)
            if case_id:
                stmt = stmt.where(AckEvent.case_id == case_id)
            stmt = stmt.order_by(AckEvent.ts.desc()).limit(limit)
            return list(db.execute(stmt).scalars().all())
