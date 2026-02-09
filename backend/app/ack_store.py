from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Ack


class AckStore:
    def upsert_ack(
        self,
        case_id: str,
        station_id: str,
        ack_scope: str,
        scope_id: str,
        user_id: str,
        comment: str | None = None,
    ) -> Ack:
        now = datetime.now(timezone.utc).isoformat()

        with SessionLocal() as db:
            existing = db.get(Ack, (case_id, station_id, ack_scope, scope_id))
            if existing:
                existing.acked_at = now
                existing.acked_by = user_id
                existing.comment = comment
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
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def get_acks_for_cases(self, case_ids: list[str], station_id: str) -> list[Ack]:
        if not case_ids:
            return []

        with SessionLocal() as db:
            stmt = select(Ack).where(
                Ack.station_id == station_id,
                Ack.case_id.in_(case_ids),
            )
            return list(db.execute(stmt).scalars().all())
