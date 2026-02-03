import { useEffect, useState } from "react";
import { fetchCases } from "./api";
import type { CaseSummary, Severity } from "./types";

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchCases()
      .then((data) => {
        setCases(data);
        setError(null);
      })
      .catch((err) => {
        console.error("fetchCases failed:", err);
        setError(err?.message ?? String(err));
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <main style={{ padding: "1rem", fontFamily: "sans-serif" }}>
      <h1>Dashboard – Station ST01</h1>

      {loading && <p>Lade Daten…</p>}
      {error && <p style={{ color: "red" }}>Fehler: {error}</p>}

      {!loading && !error && (
        <div style={{ display: "grid", gap: "0.75rem", maxWidth: 600 }}>
          {cases.map((c) => (
            <div
              key={c.case_id}
              style={{
                padding: "0.75rem 1rem",
                borderRadius: 6,
                background: severityColor(c.severity),
                border: "1px solid #ddd",
              }}
            >
              <div style={{ fontWeight: 600 }}>{c.case_id}</div>
              <div>Status: {c.severity}</div>
              {c.top_alert && (
                <div style={{ marginTop: 4, fontSize: "0.9em" }}>
                  ⚠ {c.top_alert}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
