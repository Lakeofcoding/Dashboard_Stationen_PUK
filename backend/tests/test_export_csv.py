"""
Export & CSV Tests.

Testet:
  - Export-Reports auflisten
  - Export-Daten als JSON
  - Export-Daten als CSV-Download
  - Summary-Endpunkte (taeglich/woechentlich)
  - CSV-Upload (Sample herunterladen → hochladen)
"""
import io
import pytest

pytestmark = pytest.mark.export


class TestExportReports:

    def test_list_all_reports(self, client, admin_h):
        r = client.get("/api/export/reports?frequency=all&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_list_daily_reports(self, client, admin_h):
        r = client.get("/api/export/reports?frequency=daily&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_list_weekly_reports(self, client, admin_h):
        r = client.get("/api/export/reports?frequency=weekly&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


class TestExportData:

    def test_export_data_with_report_id(self, client, admin_h):
        """Mindestens ein Report-ID sollte Daten liefern."""
        reports = client.get("/api/export/reports?ctx=Station A1", headers=admin_h).json()
        # reports kann eine Liste oder ein Dict mit "reports" key sein
        report_list = reports if isinstance(reports, list) else reports.get("reports", [])
        if not report_list:
            pytest.skip("Keine Reports konfiguriert")
        rid = report_list[0].get("id") or report_list[0].get("report_id")
        if not rid:
            pytest.skip("Kein report_id in response")
        r = client.get(f"/api/export/data?report_id={rid}&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


class TestExportSummary:

    def test_daily_summary(self, client, admin_h):
        r = client.get("/api/export/summary?frequency=daily&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_weekly_summary(self, client, admin_h):
        r = client.get("/api/export/summary?frequency=weekly&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200

    def test_summary_with_station_filter(self, client, admin_h):
        r = client.get("/api/export/summary?frequency=daily&station_id=A1&ctx=Station A1", headers=admin_h)
        assert r.status_code == 200


class TestCSVSample:

    def test_download_sample(self, client, admin_h):
        """CSV-Sample herunterladen → muss gueltig sein."""
        r = client.get("/api/admin/csv/sample?ctx=Station A1", headers=admin_h)
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert "text/csv" in content_type or "application/octet-stream" in content_type
        # Mindestens Header-Zeile
        lines = r.text.strip().split("\n")
        assert len(lines) >= 1
        assert "case_id" in lines[0]


class TestCSVUpload:

    def test_upload_valid_csv(self, client, auth):
        """CSV mit gueltigem Format hochladen."""
        import secrets
        unique_id = f"CSV_TEST_{secrets.token_hex(4)}"
        csv_content = f"case_id,station_id,patient_id,admission_date\n{unique_id},Station A1,PAT_CSV_1,2026-01-15"
        h = auth.admin()
        # Multipart braucht keinen Content-Type Header (wird automatisch gesetzt)
        h_clean = {k: v for k, v in h.items() if k != "Content-Type"}
        r = client.post(
            "/api/admin/csv/upload?ctx=Station A1",
            headers=h_clean,
            files={"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")},
        )
        assert r.status_code == 200, f"Upload failed: {r.text}"
        data = r.json()
        assert data.get("imported_rows", 0) >= 1 or data.get("total_rows", 0) >= 1, f"No rows imported: {data}"

    def test_upload_empty_csv_fails(self, client, auth):
        """Leerer CSV → sinnvolle Fehlermeldung (nicht 500)."""
        h = auth.admin()
        h_clean = {k: v for k, v in h.items() if k != "Content-Type"}
        r = client.post(
            "/api/admin/csv/upload?ctx=Station A1&station_id=A1",
            headers=h_clean,
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
        assert r.status_code != 500
