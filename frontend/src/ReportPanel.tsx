/**
 * ReportPanel – Tages- und Wochenberichte mit Export-Funktionalität.
 *
 * Zeigt eine Übersicht der definierten Report-Kategorien mit Fallzahlen
 * und ermöglicht den CSV-Export pro Kategorie.
 */

import { useEffect, useState } from "react";

interface ReportDef {
  report_id: string;
  label: string;
  category: string;
  count: number;
  case_ids: string[];
}

interface SummaryData {
  frequency: string;
  date: string;
  reports: ReportDef[];
}

interface Props {
  authHeaders: Record<string, string>;
  stationId?: string;
}

const CAT_LABELS: Record<string, string> = {
  medical: "Klinisch",
  completeness: "Kosten / Qualität",
};

const CAT_COLORS: Record<string, { bg: string; border: string; icon: string }> = {
  medical: { bg: "#eff6ff", border: "#93c5fd", icon: "🩺" },
  completeness: { bg: "#fefce8", border: "#fde047", icon: "📋" },
};

export default function ReportPanel({ authHeaders, stationId }: Props) {
  const [dailyData, setDailyData] = useState<SummaryData | null>(null);
  const [weeklyData, setWeeklyData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    const qs = stationId ? `&station_id=${stationId}` : "";

    Promise.all([
      fetch(`/api/export/summary?frequency=daily${qs}`, { headers: authHeaders }).then((r) => r.json()),
      fetch(`/api/export/summary?frequency=weekly${qs}`, { headers: authHeaders }).then((r) => r.json()),
    ])
      .then(([d, w]) => {
        if (!cancelled) {
          setDailyData(d);
          setWeeklyData(w);
        }
      })
      .catch(console.error)
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [stationId]);

  if (loading) return <div style={{ color: "#999", padding: 16 }}>Lade Berichte…</div>;

  const renderSection = (title: string, emoji: string, data: SummaryData | null) => {
    if (!data) return null;

    // Group by category
    const grouped: Record<string, ReportDef[]> = {};
    for (const r of data.reports) {
      const cat = r.category;
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(r);
    }

    const totalIssues = data.reports.reduce((s, r) => s + r.count, 0);

    return (
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 20 }}>{emoji}</span>
          <h3 style={{ margin: 0, fontSize: "1.1rem" }}>{title}</h3>
          <span style={{
            fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999,
            background: totalIssues > 0 ? "#fef2f2" : "#f0fdf4",
            color: totalIssues > 0 ? "#dc2626" : "#16a34a",
            border: `1px solid ${totalIssues > 0 ? "#fca5a5" : "#86efac"}`,
          }}>
            {totalIssues} {totalIssues === 1 ? "Auffälligkeit" : "Auffälligkeiten"}
          </span>
          <span style={{ fontSize: 12, color: "#9ca3af" }}>{data.date}</span>
        </div>

        {Object.entries(grouped).map(([cat, reports]) => {
          const catConf = CAT_COLORS[cat] || CAT_COLORS.medical;
          return (
            <div key={cat} style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 6 }}>
                {catConf.icon} {CAT_LABELS[cat] ?? cat}
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                {reports.map((r) => {
                  const isExpanded = expandedReport === r.report_id;
                  const qs = stationId ? `&station_id=${stationId}` : "";
                  const csvUrl = `/api/export/csv?report_id=${r.report_id}${qs}`;
                  // Add auth headers as query params for CSV download link
                  const csvHeaders = new URLSearchParams(authHeaders).toString();

                  return (
                    <div key={r.report_id}>
                      <div
                        onClick={() => setExpandedReport(isExpanded ? null : r.report_id)}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 12px",
                          borderRadius: 8,
                          background: r.count > 0 ? catConf.bg : "#f9fafb",
                          border: `1px solid ${r.count > 0 ? catConf.border : "#e5e7eb"}`,
                          cursor: "pointer",
                          transition: "background 0.15s",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{
                            width: 28, height: 28, borderRadius: "50%",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 13, fontWeight: 800,
                            background: r.count > 0 ? "#ef4444" : "#d1d5db",
                            color: "white",
                          }}>
                            {r.count}
                          </span>
                          <span style={{ fontSize: 13, fontWeight: 500 }}>{r.label}</span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          {r.count > 0 && (
                            <a
                              href={csvUrl}
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                fontSize: 11, padding: "3px 8px", borderRadius: 4,
                                background: "#fff", border: "1px solid #d1d5db",
                                color: "#374151", textDecoration: "none", fontWeight: 600,
                              }}
                            >
                              CSV ↓
                            </a>
                          )}
                          <span style={{ fontSize: 14, color: "#9ca3af", transform: isExpanded ? "rotate(180deg)" : "", transition: "transform 0.15s" }}>▼</span>
                        </div>
                      </div>

                      {isExpanded && r.count > 0 && (
                        <div style={{
                          padding: "8px 14px", marginTop: 2, borderRadius: "0 0 8px 8px",
                          background: "#fff", border: "1px solid #e5e7eb", borderTop: "none",
                          fontSize: 12, color: "#374151",
                        }}>
                          <strong>Fallnummern:</strong>{" "}
                          {r.case_ids.join(", ")}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div>
      {renderSection("Tagesbericht", "📊", dailyData)}
      {renderSection("Wochenbericht", "📅", weeklyData)}
    </div>
  );
}
