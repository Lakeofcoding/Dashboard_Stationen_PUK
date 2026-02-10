from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Ack, AckEvent, Defer


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
                }

                existing.acked_at = now
                existing.acked_by = user_id
                existing.comment = comment
                # NEW
                existing.condition_hash = condition_hash

                db.add(
                    self._insert_event(
                        case_id=case_id,
                        station_id=station_id,
                        ack_scope=ack_scope,
                        scope_id=scope_id,
                        event_type="ACK_UPDATE",
                        user_id=user_id,
                        payload={
                            "old": old,
                            "new": {
                                "acked_at": now,
                                "acked_by": user_id,
                                "comment": comment,
                                "condition_hash": condition_hash,
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
                # NEW
                condition_hash=condition_hash,
            )
            db.add(row)

            db.add(
                self._insert_event(
                    case_id=case_id,
                    station_id=station_id,
                    ack_scope=ack_scope,
                    scope_id=scope_id,
                    event_type="ACK",
                    user_id=user_id,
                    payload={
                        "acked_at": now,
                        "acked_by": user_id,
                        "comment": comment,
                        "condition_hash": condition_hash,
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

    # ---------------------------------------------------------------------
    # Defer ("Schieben")
    # ---------------------------------------------------------------------

    def upsert_defer(
        self,
        *,
        case_id: str,
        station_id: str,
        user_id: str,
        reason: str,
    ) -> Defer:
        """Speichert/aktualisiert den "geschoben"-Status.

        Zusätzlich schreiben wir einen Audit-Eintrag in ack_event.
        """
        now = _now_iso()

        with SessionLocal() as db:
            existing = db.get(Defer, (case_id, station_id))

            if existing:
                old = {"deferred_at": existing.deferred_at, "deferred_by": existing.deferred_by, "reason": existing.reason}

                existing.deferred_at = now
                existing.deferred_by = user_id
                existing.reason = reason

                db.add(
                    self._insert_event(
                        case_id=case_id,
                        station_id=station_id,
                        ack_scope="case",
                        scope_id="*",
                        event_type="DEFER_UPDATE",
                        user_id=user_id,
                        payload={"old": old, "new": {"deferred_at": now, "deferred_by": user_id, "reason": reason}},
                    )
                )

                db.commit()
                db.refresh(existing)
                return existing

            row = Defer(
                case_id=case_id,
                station_id=station_id,
                deferred_at=now,
                deferred_by=user_id,
                reason=reason,
            )

            db.add(row)
            db.add(
                self._insert_event(
                    case_id=case_id,
                    station_id=station_id,
                    ack_scope="case",
                    scope_id="*",
                    event_type="DEFER",
                    user_id=user_id,
                    payload={"deferred_at": now, "deferred_by": user_id, "reason": reason},
                )
            )
            db.commit()
            db.refresh(row)
            return row

    def get_defers_for_cases(self, case_ids: list[str], station_id: str) -> dict[str, Defer]:
        """Liefert den aktuellen "geschoben"-Status (falls vorhanden) pro case_id."""
        if not case_ids:
            return {}

        with SessionLocal() as db:
            stmt = select(Defer).where(Defer.station_id == station_id, Defer.case_id.in_(case_ids))
            rows = list(db.execute(stmt).scalars().all())
            return {r.case_id: r for r in rows}
