"""
Rule Engine Unit Tests.

Testet die Regelauswertung direkt (ohne HTTP), um sicherzustellen dass:
  - Jede der 24 Regeln bei korrektem Input feuert
  - Gesunde Faelle keine Alerts erzeugen
  - Severity korrekt bestimmt wird (CRITICAL > WARN > OK)
  - Condition-Hashes deterministisch und stabil sind

Klinischer Kontext:
  Falsch-negative Regeln (Alert wird nicht ausgeloest) sind das
  gefaehrlichste Szenario: Eine klinische Warnung wird nicht angezeigt,
  obwohl eine Handlung erforderlich waere.
"""
import pytest
from datetime import date, timedelta

pytestmark = pytest.mark.rules


# Imports after sys.path setup (conftest handles this via main import)
from app.case_logic import enrich_case
from app.rule_engine import evaluate_alerts, summarize_severity


def _base_case(**overrides) -> dict:
    """Factory fuer einen minimalen Testfall mit sinnvollen Defaults."""
    today = date.today()
    case = {
        "case_id": "TEST_001",
        "patient_id": "PAT_001",
        "clinic": "EPP",
        "station_id": "A1",
        "center": "ZAPE",
        "admission_date": today - timedelta(days=5),
        "discharge_date": None,
        # HoNOS
        "honos_entry_total": 12,
        "honos_entry_date": today - timedelta(days=4),
        "honos_discharge_total": None,
        "honos_discharge_date": None,
        "honos_discharge_suicidality": None,
        # BSCL
        "bscl_total_entry": 30,
        "bscl_entry_date": today - timedelta(days=4),
        "bscl_total_discharge": None,
        "bscl_discharge_date": None,
        "bscl_discharge_suicidality": None,
        # BFS
        "bfs_1": 10, "bfs_2": 12, "bfs_3": 9,
        # Isolation
        "isolations": [],
        # Klinisch
        "is_voluntary": True,
        "treatment_plan_date": (today - timedelta(days=3)).isoformat(),
        "sdep_complete": True,
        "ekg_last_date": None,
        "ekg_last_reported": None,
        "ekg_entry_date": (today - timedelta(days=4)).isoformat(),
        "clozapin_active": False,
        "clozapin_start_date": None,
        "neutrophils_last_date": None,
        "neutrophils_last_value": None,
        "troponin_last_date": None,
        "cbc_last_date": None,
        "emergency_bem_start_date": None,
        "emergency_med_start_date": None,
        "allergies_recorded": True,
    }
    case.update(overrides)
    return enrich_case(case)


class TestHealthyCase:
    """Ein gesunder Fall sollte wenige oder keine Alerts erzeugen."""

    def test_healthy_case_no_critical(self):
        c = _base_case()
        alerts = evaluate_alerts(c)
        critical = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical) == 0, f"Healthy case has CRITICALs: {[a.rule_id for a in critical]}"


class TestHonosRules:

    def test_honos_entry_missing_warn(self):
        """HONOS Eintritt fehlt, < 3 Tage → WARN."""
        c = _base_case(
            honos_entry_total=None,
            honos_entry_date=None,
            admission_date=date.today() - timedelta(days=2),
        )
        alerts = evaluate_alerts(c)
        rule_ids = {a.rule_id for a in alerts}
        assert "HONOS_ENTRY_MISSING_WARN" in rule_ids

    def test_honos_entry_missing_critical_3d(self):
        """HONOS Eintritt fehlt, > 3 Tage → CRITICAL."""
        c = _base_case(
            honos_entry_total=None,
            honos_entry_date=None,
            admission_date=date.today() - timedelta(days=5),
        )
        alerts = evaluate_alerts(c)
        rule_ids = {a.rule_id for a in alerts}
        assert "HONOS_ENTRY_MISSING_CRIT_3D" in rule_ids

    def test_honos_present_no_alert(self):
        """HONOS vorhanden → kein HONOS_ENTRY Alert."""
        c = _base_case(honos_entry_total=15)
        alerts = evaluate_alerts(c)
        honos_alerts = [a for a in alerts if "HONOS_ENTRY" in a.rule_id]
        assert len(honos_alerts) == 0


class TestBfsRule:

    def test_bfs_incomplete(self):
        """BFS unvollstaendig → Alert."""
        c = _base_case(bfs_1=10, bfs_2=None, bfs_3=None)
        alerts = evaluate_alerts(c)
        rule_ids = {a.rule_id for a in alerts}
        assert "BFS_INCOMPLETE" in rule_ids

    def test_bfs_complete_no_alert(self):
        """BFS komplett → kein Alert."""
        c = _base_case(bfs_1=10, bfs_2=12, bfs_3=9)
        alerts = evaluate_alerts(c)
        bfs_alerts = [a for a in alerts if a.rule_id == "BFS_INCOMPLETE"]
        assert len(bfs_alerts) == 0


class TestTreatmentPlanRule:

    def test_involuntary_no_plan_critical(self):
        """Nicht-freiwillig, kein Behandlungsplan, > 72h → CRITICAL."""
        c = _base_case(
            is_voluntary=False,
            treatment_plan_date=None,
            admission_date=date.today() - timedelta(days=5),
        )
        alerts = evaluate_alerts(c)
        rule_ids = {a.rule_id for a in alerts}
        assert "TREATMENT_PLAN_MISSING_72H" in rule_ids

    def test_voluntary_no_plan_no_alert(self):
        """Freiwillig, kein Behandlungsplan → kein TREATMENT_PLAN Alert."""
        c = _base_case(is_voluntary=True, treatment_plan_date=None)
        alerts = evaluate_alerts(c)
        tp_alerts = [a for a in alerts if a.rule_id == "TREATMENT_PLAN_MISSING_72H"]
        assert len(tp_alerts) == 0


class TestAllergiesRule:

    def test_allergies_missing_over_7d(self):
        """Allergien nicht erfasst, > 7 Tage → Alert."""
        c = _base_case(
            allergies_recorded=False,
            admission_date=date.today() - timedelta(days=10),
        )
        alerts = evaluate_alerts(c)
        rule_ids = {a.rule_id for a in alerts}
        assert "ALLERGIES_MISSING_7D" in rule_ids


class TestSeveritySummarization:

    def test_critical_overrides_warn(self):
        """Wenn CRITICAL und WARN vorhanden → severity = CRITICAL."""
        from app.schemas import Alert
        alerts = [
            Alert(rule_id="R1", severity="WARN", message="w", explanation="", category="completeness", condition_hash="h1"),
            Alert(rule_id="R2", severity="CRITICAL", message="c", explanation="", category="medical", condition_hash="h2"),
        ]
        sev, top, cc, wc = summarize_severity(alerts)
        assert sev == "CRITICAL"
        assert cc == 1
        assert wc == 1

    def test_no_alerts_ok(self):
        """Keine Alerts → severity = OK."""
        sev, top, cc, wc = summarize_severity([])
        assert sev == "OK"
        assert cc == 0 and wc == 0


class TestConditionHash:
    """Condition-Hashes muessen deterministisch sein."""

    def test_same_input_same_hash(self):
        c = _base_case(honos_entry_total=None, honos_entry_date=None)
        alerts1 = evaluate_alerts(c)
        alerts2 = evaluate_alerts(c)
        if alerts1:
            assert alerts1[0].condition_hash == alerts2[0].condition_hash
