import { useEffect, useState } from "react";
import type { CaseSummary, CaseDetail, Severity } from "./types";
import { Toast } from "./Toast";
import { fetchCases, fetchCaseDetail, ackCase } from "./api";



function severityColor(severity: Severity): string {
  switch (severity) {
    case "CRITICAL":
      return "#ffe5e5";
    case "WARN":
      return "#fff6d6";
    default:
      return "#e8f5e9";
  }
}

export default function App() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [toast, setToast] = useState<{ caseId: string; message: string; kind: "critical" | "warn" | "info" } | null>(null);
  const [shownCritical, setShownCritical] = useState<Record<string, true>>({});


  useEffect(() => {
    fetchCases()
  .then((data) => {
    setCases(data);
    setError(null);

    // Find first CRITICAL case that hasn't shown a toast yet
    const firstCritical = data.find((c) => c.severity === "CRITICAL" && !c.acked_at && !shownCritical[c.case_id]);
    if (firstCritical) {
      setToast({
  kind: "critical",
  caseId: firstCritical.case_id,
  message: `${firstCritical.case_id}: ${firstCritical.top_alert ?? "Kritischer Status"}`,
});

      setShownCritical((prev) => ({ ...prev, [firstCritical.case_id]: true }));
    }
  })
  .catch((err) => setError(err?.message ?? String(err)));
  }, [shownCritical]);

  useEffect(() => {
    if (!selectedCaseId) {
      setDetail(null);
      setDetailError(null);
      return;
    }

    setDetailLoading(true);
    fetchCaseDetail(selectedCaseId)
      .then((d) => {
        setDetail(d);
        setDetailError(null);
      })
      .catch((err) => setDetailError(err?.message ?? String(err)))
      .finally(() => setDetailLoading(false));
  }, [selectedCaseId]);

  return (
    <main style={{ padding: "1rem", fontFamily: "sans-serif" }}>
      <h1>Dashboard – Station ST01</h1>

      {error && <p style={{ color: "red" }}>Fehler: {error}</p>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: "1rem", alignItems: "start" }}>
        {/* Left: Cards */}
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {cases.map((c) => (
            <button
              key={c.case_id}
              onClick={() => setSelectedCaseId(c.case_id)}
              style={{
                textAlign: "left",
                padding: "0.75rem 1rem",
                borderRadius: 6,
                background: severityColor(c.severity),
                border: selectedCaseId === c.case_id ? "2px solid #333" : "1px solid #ddd",
                cursor: "pointer",
              }}
            >
              <div style={{ fontWeight: 700 }}>{c.case_id}</div>
              <div>Status: {c.severity}</div>
              {c.top_alert && <div style={{ marginTop: 4 }}>⚠ {c.top_alert}</div>}
            </button>
          ))}
        </div>

        {/* Right: Detail Panel */}
        <aside
          style={{
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: "0.75rem 1rem",
            background: "#fff",
            minHeight: 200,
          }}
        >
          {!selectedCaseId && <p>Fall auswählen, um Details zu sehen.</p>}

          {selectedCaseId && detailLoading && <p>Lade Details…</p>}

          {selectedCaseId && detailError && <p style={{ color: "red" }}>Fehler: {detailError}</p>}

          {detail && !detailLoading && !detailError && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <h2 style={{ margin: 0, fontSize: "1.1rem" }}>{detail.case_id}</h2>
                <button onClick={() => setSelectedCaseId(null)}>✕</button>
              </div>
              <p>
              <strong>Quittiert:</strong> {detail.acked_at ? `Ja (${detail.acked_at})` : "Nein"}
            </p>

            {detail.severity === "CRITICAL" && !detail.acked_at && (
              <button
  onClick={async () => {
    try {
      const res = await ackCase(detail.case_id);

      setDetail({
        ...detail,
        acked_at: res.acked_at,
      });

      const list = await fetchCases();
      setCases(list);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    }
  }}
  style={{
    marginTop: 8,
    padding: "8px 12px",
    borderRadius: 6,
    border: "1px solid #b71c1c",
    background: "#d32f2f",
    color: "white",
    fontWeight: 600,
    cursor: "pointer",
  }}
>
  Fall quittieren
</button>



            )}


              <p style={{ marginTop: 8 }}>
                <strong>Station:</strong> {detail.station_id}
                <br />
                <strong>Eintritt:</strong> {detail.admission_date}
                <br />
                <strong>HONOS:</strong> {detail.honos ?? "—"}
                <br />
                <strong>BSCL:</strong> {detail.bscl ?? "—"}
                <br />
                <strong>BFS vollständig:</strong> {detail.bfs_complete ? "Ja" : "Nein"}
              </p>

              <h3 style={{ marginBottom: 6, fontSize: "1rem" }}>Alerts</h3>
              {detail.alerts.length === 0 ? (
                <p>Keine Alerts.</p>
              ) : (
                <ul style={{ paddingLeft: 18, marginTop: 0 }}>
                  {detail.alerts.map((a) => (
                    <li key={a.rule_id}>
                      <strong>{a.severity}:</strong> {a.message}
                      <div style={{ fontSize: "0.9em", opacity: 0.9 }}>{a.explanation}</div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </aside>
      </div>
      {toast && (
  <Toast
    kind={toast.kind}
    message={toast.message}
    actionLabel="Quittieren"
    onAction={async () => {
      try {
        await ackCase(toast.caseId);
        setToast(null);
        // reload cases so acked_at becomes visible and toast won't reappear
        const data = await fetchCases();
        setCases(data);
      } catch (e: any) {
        setError(e?.message ?? String(e));
      }
    }}
    onClose={() => setToast(null)}
  />
)}

    </main>
  );
}
