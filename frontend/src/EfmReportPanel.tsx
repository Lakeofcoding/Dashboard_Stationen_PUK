import { useState, useEffect, forwardRef, useImperativeHandle, useMemo } from "react";
import type { ReportPanelHandle } from "./HonosReportPanel";

/* ─── Types ─── */
interface ByType { count: number; avg_h: number | null; max_h: number | null; median_h: number | null; }
interface ClinicRow { clinic: string; n_efm: number; n_cases: number; }
interface StationRow { station: string; klinik: string; zentrum: string; n_efm: number; n_cases: number; }
interface TimelinePoint { month: string; count: number; n_cases: number; }
interface TopPatient { fid: number; count: number; station: string; }
interface Alert { type: string; severity: string; efm_id: number; fid: number; art: string; station: string; msg: string; }
interface EfmEntry { efm_id: number; fid: number; pid: string; station: string; klinik: string; zentrum: string; art_efm: string; start_dt: string | null; end_dt: string | null; duration_h: number | null; angeordnet_von: string | null; begruendung: string | null; }
interface Hierarchy { [clinic: string]: { [center: string]: string[] } }
interface KPIs { total_efm: number; cases_with_efm: number; total_cases: number; efm_rate_pct: number; n_isolation: number; n_fixierung: number; n_festhalten: number; n_zwangsmed: number; n_alerts_critical: number; n_alerts_warning: number; }
interface EfmData {
  kpis: KPIs; by_type: Record<string, ByType>; by_clinic: ClinicRow[]; by_station: StationRow[];
  timeline: TimelinePoint[]; top_patients: TopPatient[]; alerts: Alert[];
  efm_list: EfmEntry[]; hierarchy: Hierarchy; available_months: string[];
}

interface Props { auth: { token: string }; canView: boolean; monat: string; onMonatChange: (m: string) => void; }

/* ─── Helpers ─── */
const CC: Record<string, string> = { EPP: "#2563eb", FPP: "#dc2626", APP: "#059669", KJPP: "#d97706" };
const cc = (k: string) => CC[k] ?? "#6b7280";
const fmt = (v: number | null, d = 1) => v == null ? "–" : v.toFixed(d);
const TYPE_COLORS: Record<string, string> = {
  "Isolation": "#7c3aed", "Fixierung": "#dc2626", "Festhalten": "#d97706",
  "Zwangsmedikation oral": "#059669", "Zwangsmedikation Injektion": "#2563eb",
};

/* ─── KPI Card ─── */
function KPI({ label, value, sub, color, unit }: { label: string; value: string; sub?: string; color?: string; unit?: string }) {
  return (
    <div style={{ flex: "1 1 110px", background: "#fff", borderRadius: 12, padding: "12px 14px",
      border: "1px solid #e5e7eb", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
      <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color ?? "#111827", letterSpacing: -0.5 }}>
        {value}{unit && <span style={{ fontSize: 12, fontWeight: 600, marginLeft: 2 }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 9, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* ─── Main Panel ─── */
const EfmReportPanel = forwardRef<ReportPanelHandle, Props>(function EfmReportPanel({ auth, canView, monat, onMonatChange }, ref) {
  const [data, setData] = useState<EfmData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [drillClinic, setDrillClinic] = useState<string | null>(null);
  const [drillCenter, setDrillCenter] = useState<string | null>(null);
  const [drillStation, setDrillStation] = useState<string | null>(null);
  const [alertFilter, setAlertFilter] = useState<"all" | "critical" | "warning">("all");

  useImperativeHandle(ref, () => ({
    canGoBack: () => !!(drillStation || drillCenter || drillClinic),
    goBack: () => {
      if (drillStation) setDrillStation(null);
      else if (drillCenter) setDrillCenter(null);
      else if (drillClinic) setDrillClinic(null);
    },
  }), [drillClinic, drillCenter, drillStation]);

  useEffect(() => {
    if (!canView) return;
    setLoading(true);
    const params = new URLSearchParams();
    if (drillClinic) params.set("clinic", drillClinic);
    if (drillCenter) params.set("center", drillCenter);
    if (drillStation) params.set("station", drillStation);
    if (monat) params.set("monat", monat);
    const qs = params.toString();
    fetch(`/api/reporting/efm${qs ? "?" + qs : ""}`, {
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${auth.token}` },
    })
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(d => { setData(d); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [auth.token, canView, drillClinic, drillCenter, drillStation, monat]);

  if (!canView) return <div style={{ padding: 32, color: "#9ca3af" }}>Kein Zugriff auf Reporting (Scope zu niedrig).</div>;
  if (loading) return <div style={{ padding: 32, color: "#6b7280" }}>Lade EFM-Daten…</div>;
  if (error) return <div style={{ padding: 32, color: "#dc2626" }}>Fehler: {error}</div>;
  if (!data) return null;

  const { kpis, by_type, by_clinic, by_station, timeline, top_patients, alerts, efm_list, hierarchy, available_months } = data;
  const typeKeys = Object.keys(by_type);

  const breadcrumb = [
    { label: "Alle Kliniken", active: !drillClinic, onClick: () => { setDrillClinic(null); setDrillCenter(null); setDrillStation(null); } },
    drillClinic ? { label: drillClinic, active: !drillCenter, onClick: () => { setDrillCenter(null); setDrillStation(null); } } : null,
    drillCenter ? { label: drillCenter, active: !drillStation, onClick: () => setDrillStation(null) } : null,
    drillStation ? { label: drillStation, active: true, onClick: () => {} } : null,
  ].filter(Boolean) as { label: string; active: boolean; onClick: () => void }[];

  const filteredAlerts = alerts.filter(a => alertFilter === "all" || a.severity === alertFilter);
  const maxTypeCount = Math.max(...Object.values(by_type).map(t => t.count), 1);

  return (
    <div style={{ padding: "0 4px" }}>
      <h2 style={{ fontSize: 18, fontWeight: 800, margin: "0 0 4px" }}>
        ⚠️ EFM Reporting <span style={{ fontWeight: 400, fontSize: 13, color: "#6b7280" }}>Freiheitsbeschränkende Massnahmen</span>
      </h2>
      <p style={{ margin: "0 0 14px", fontSize: 11, color: "#9ca3af" }}>
        ANQ-konform · Isolation, Fixierung, Festhalten, Zwangsmedikation · SAMW/NKVF Monitoring-Regeln
      </p>

      {/* Month filter */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "#6b7280" }}>Monat:</span>
        <button onClick={() => onMonatChange("")}
          style={{ padding: "4px 10px", borderRadius: 6, fontSize: 11, cursor: "pointer",
            background: !monat ? "#7c3aed" : "#f3f4f6", color: !monat ? "#fff" : "#374151",
            border: !monat ? "1px solid #7c3aed" : "1px solid #d1d5db" }}>Alle</button>
        {available_months.slice(0, 12).map(m => (
          <button key={m} onClick={() => onMonatChange(m)}
            style={{ padding: "4px 10px", borderRadius: 6, fontSize: 11, cursor: "pointer",
              background: monat === m ? "#7c3aed" : "#f3f4f6", color: monat === m ? "#fff" : "#374151",
              border: monat === m ? "1px solid #7c3aed" : "1px solid #d1d5db" }}>{m}</button>
        ))}
      </div>

      {/* Breadcrumb */}
      <div style={{ fontSize: 12, marginBottom: 10, color: "#7c3aed" }}>
        {breadcrumb.map((b, i) => (
          <span key={i}>
            {i > 0 && <span style={{ color: "#d1d5db" }}> → </span>}
            <span onClick={b.onClick} style={{ cursor: b.active ? "default" : "pointer",
              fontWeight: b.active ? 700 : 400, textDecoration: b.active ? "none" : "underline" }}>{b.label}</span>
          </span>
        ))}
      </div>

      {/* Clinic cards (drill-down) */}
      {!drillClinic && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 10, marginBottom: 16 }}>
          {by_clinic.map(c => (
            <div key={c.clinic} onClick={() => setDrillClinic(c.clinic)}
              style={{ padding: "10px 14px", borderRadius: 10, cursor: "pointer", background: "#fff",
                border: `2px solid ${cc(c.clinic)}22`, fontSize: 13 }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = cc(c.clinic); }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = cc(c.clinic) + "22"; }}>
              <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%",
                background: cc(c.clinic), marginRight: 6 }} />
              <strong>{c.clinic}</strong>
              <div style={{ fontSize: 10, color: "#6b7280", marginTop: 4 }}>{c.n_efm} EFM · {c.n_cases} Fälle</div>
            </div>
          ))}
        </div>
      )}

      {/* Center/Station drill */}
      {drillClinic && !drillCenter && hierarchy[drillClinic] && Object.keys(hierarchy[drillClinic]).length > 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 10, marginBottom: 16 }}>
          {Object.keys(hierarchy[drillClinic]).sort().map(ctr => (
            <div key={ctr} onClick={() => setDrillCenter(ctr)}
              style={{ padding: "10px 14px", borderRadius: 10, cursor: "pointer", background: "#fff",
                border: "1px solid #e5e7eb", fontSize: 13 }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "#7c3aed"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb"; }}>
              <strong>{ctr}</strong>
            </div>
          ))}
        </div>
      )}
      {drillCenter && !drillStation && hierarchy[drillClinic!]?.[drillCenter] && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(180px,1fr))", gap: 10, marginBottom: 16 }}>
          {hierarchy[drillClinic!][drillCenter].sort().map(st => {
            const sd = by_station.find(s => s.station === st);
            return (
              <div key={st} onClick={() => setDrillStation(st)}
                style={{ padding: "10px 14px", borderRadius: 10, cursor: "pointer", background: "#fff",
                  border: "1px solid #e5e7eb", fontSize: 13 }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "#7c3aed"; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb"; }}>
                <strong>{st}</strong>
                {sd && <div style={{ fontSize: 10, color: "#9ca3af" }}>{sd.n_efm} EFM · {sd.n_cases} Fälle</div>}
              </div>
            );
          })}
        </div>
      )}

      {/* KPI Cards */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 18 }}>
        <KPI label="EFM gesamt" value={String(kpis.total_efm)} />
        <KPI label="Fälle mit EFM" value={String(kpis.cases_with_efm)} sub={`${kpis.efm_rate_pct}% von ${kpis.total_cases}`} color="#7c3aed" />
        <KPI label="Isolationen" value={String(kpis.n_isolation)} color={TYPE_COLORS["Isolation"]} />
        <KPI label="Fixierungen" value={String(kpis.n_fixierung)} color={TYPE_COLORS["Fixierung"]} />
        <KPI label="Festhalten" value={String(kpis.n_festhalten)} color={TYPE_COLORS["Festhalten"]} />
        <KPI label="Zwangsmed." value={String(kpis.n_zwangsmed)} color={TYPE_COLORS["Zwangsmedikation oral"]} />
        <KPI label="Alerts" value={String(kpis.n_alerts_critical + kpis.n_alerts_warning)}
          color={kpis.n_alerts_critical > 0 ? "#dc2626" : kpis.n_alerts_warning > 0 ? "#d97706" : "#059669"}
          sub={`${kpis.n_alerts_critical} kritisch · ${kpis.n_alerts_warning} Warnung`} />
      </div>

      {/* Type breakdown (horizontal bars) */}
      <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>EFM nach Art</h3>
        {typeKeys.map(t => {
          const d = by_type[t];
          const pct = (d.count / maxTypeCount) * 100;
          return (
            <div key={t} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <div style={{ width: 160, fontSize: 11, color: "#374151", flexShrink: 0 }}>{t}</div>
              <div style={{ flex: 1, height: 18, background: "#f3f4f6", borderRadius: 4, position: "relative" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: TYPE_COLORS[t] || "#6b7280",
                  borderRadius: 4, transition: "width .3s", minWidth: d.count > 0 ? 2 : 0 }} />
              </div>
              <div style={{ width: 30, fontSize: 12, fontWeight: 700, textAlign: "right" }}>{d.count}</div>
              <div style={{ width: 80, fontSize: 9, color: "#9ca3af" }}>
                {d.avg_h != null ? `Ø ${fmt(d.avg_h)}h` : "–"}
                {d.max_h != null ? ` · max ${fmt(d.max_h)}h` : ""}
              </div>
            </div>
          );
        })}
      </div>

      {/* Timeline (monthly) */}
      {timeline.length > 1 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 700 }}>Verlauf (monatlich)</h3>
          <div style={{ display: "flex", alignItems: "end", gap: 4, height: 120 }}>
            {timeline.map(p => {
              const maxC = Math.max(...timeline.map(t => t.count), 1);
              const h = (p.count / maxC) * 100;
              return (
                <div key={p.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div style={{ fontSize: 9, fontWeight: 700, color: "#7c3aed", marginBottom: 2 }}>{p.count}</div>
                  <div style={{ width: "80%", height: h, background: "#7c3aed", borderRadius: "3px 3px 0 0",
                    transition: "height .3s", minHeight: 2 }}
                    title={`${p.month}: ${p.count} EFM, ${p.n_cases} Fälle`} />
                  <div style={{ fontSize: 8, color: "#9ca3af", marginTop: 3, transform: "rotate(-45deg)", whiteSpace: "nowrap" }}>
                    {p.month.slice(5)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quality Alerts */}
      {alerts.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>
              🚨 Qualitäts-Alerts ({alerts.length})
            </h3>
            <div style={{ display: "flex", gap: 4 }}>
              {(["all", "critical", "warning"] as const).map(f => (
                <button key={f} onClick={() => setAlertFilter(f)}
                  style={{ padding: "3px 8px", borderRadius: 4, fontSize: 10, cursor: "pointer",
                    background: alertFilter === f ? (f === "critical" ? "#fef2f2" : f === "warning" ? "#fffbeb" : "#f3f4f6") : "#fff",
                    border: `1px solid ${alertFilter === f ? (f === "critical" ? "#fecaca" : f === "warning" ? "#fde68a" : "#d1d5db") : "#e5e7eb"}`,
                    color: f === "critical" ? "#dc2626" : f === "warning" ? "#d97706" : "#374151" }}>
                  {f === "all" ? `Alle (${alerts.length})` : f === "critical" ? `Kritisch (${kpis.n_alerts_critical})` : `Warnung (${kpis.n_alerts_warning})`}
                </button>
              ))}
            </div>
          </div>
          <div style={{ maxHeight: 300, overflowY: "auto" }}>
            {filteredAlerts.slice(0, 50).map((a, i) => (
              <div key={i} style={{ display: "flex", gap: 8, padding: "6px 0", borderBottom: "1px solid #f3f4f6",
                fontSize: 11, alignItems: "center" }}>
                <span style={{ width: 16, height: 16, borderRadius: "50%", flexShrink: 0, display: "flex",
                  alignItems: "center", justifyContent: "center", fontSize: 10,
                  background: a.severity === "critical" ? "#fef2f2" : "#fffbeb",
                  color: a.severity === "critical" ? "#dc2626" : "#d97706" }}>
                  {a.severity === "critical" ? "!" : "⚠"}
                </span>
                <span style={{ color: "#374151", flex: 1 }}>{a.msg}</span>
                <span style={{ color: "#9ca3af", fontSize: 10, whiteSpace: "nowrap" }}>Fall {a.fid} · {a.station}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top patients */}
      {top_patients.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700 }}>Fälle mit häufigsten EFM</h3>
          <div style={{ display: "grid", gridTemplateColumns: "60px 1fr 60px 60px", gap: "1px", fontSize: 11 }}>
            <div style={{ fontWeight: 700, color: "#6b7280", padding: "4px" }}>Fall</div>
            <div style={{ fontWeight: 700, color: "#6b7280", padding: "4px" }}>Station</div>
            <div style={{ fontWeight: 700, color: "#6b7280", padding: "4px", textAlign: "center" }}>Anzahl</div>
            <div style={{ fontWeight: 700, color: "#6b7280", padding: "4px" }}></div>
            {top_patients.slice(0, 10).map(p => {
              const maxN = top_patients[0]?.count || 1;
              const pct = (p.count / maxN) * 100;
              return [
                <div key={`f${p.fid}`} style={{ padding: "4px", fontFamily: "monospace", fontSize: 10 }}>{p.fid}</div>,
                <div key={`s${p.fid}`} style={{ padding: "4px", color: "#374151" }}>{p.station}</div>,
                <div key={`n${p.fid}`} style={{ padding: "4px", textAlign: "center", fontWeight: 700,
                  color: p.count >= 4 ? "#dc2626" : p.count >= 2 ? "#d97706" : "#374151" }}>{p.count}</div>,
                <div key={`b${p.fid}`} style={{ padding: "4px" }}>
                  <div style={{ height: 10, width: `${pct}%`, background: p.count >= 4 ? "#fecaca" : "#e5e7eb",
                    borderRadius: 2, minWidth: 4 }} />
                </div>,
              ];
            })}
          </div>
        </div>
      )}

      {/* EFM Einzelliste */}
      <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
        <h3 style={{ margin: "0 0 10px", fontSize: 14, fontWeight: 700 }}>EFM Massnahmen ({efm_list.length})</h3>
        <div style={{ maxHeight: 400, overflowY: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 10 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb" }}>
                <th style={{ padding: "4px 6px", textAlign: "left" }}>Art</th>
                <th style={{ padding: "4px 6px", textAlign: "left" }}>Fall</th>
                <th style={{ padding: "4px 6px", textAlign: "left" }}>Station</th>
                <th style={{ padding: "4px 6px", textAlign: "left" }}>Start</th>
                <th style={{ padding: "4px 6px", textAlign: "left" }}>Ende</th>
                <th style={{ padding: "4px 6px", textAlign: "right" }}>Dauer</th>
              </tr>
            </thead>
            <tbody>
              {efm_list.map(e => (
                <tr key={e.efm_id} style={{ borderBottom: "1px solid #f3f4f6" }}>
                  <td style={{ padding: "4px 6px" }}>
                    <span style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%",
                      background: TYPE_COLORS[e.art_efm] || "#6b7280", marginRight: 4 }} />
                    {e.art_efm}
                  </td>
                  <td style={{ padding: "4px 6px", fontFamily: "monospace" }}>{e.fid}</td>
                  <td style={{ padding: "4px 6px" }}>{e.station}</td>
                  <td style={{ padding: "4px 6px" }}>{e.start_dt ? e.start_dt.replace("T", " ").slice(0, 16) : "–"}</td>
                  <td style={{ padding: "4px 6px", color: e.end_dt ? "#374151" : "#dc2626", fontWeight: e.end_dt ? 400 : 700 }}>
                    {e.end_dt ? e.end_dt.replace("T", " ").slice(0, 16) : "OFFEN ⚠"}
                  </td>
                  <td style={{ padding: "4px 6px", textAlign: "right",
                    color: e.duration_h != null && e.duration_h > 72 ? "#dc2626" : e.duration_h != null && e.duration_h > 24 ? "#d97706" : "#374151",
                    fontWeight: e.duration_h != null && e.duration_h > 24 ? 700 : 400 }}>
                    {e.duration_h != null ? `${fmt(e.duration_h)}h` : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Methodik */}
      <div style={{ background: "#f3f0ff", borderRadius: 10, padding: "10px 14px", fontSize: 10, color: "#6b7280" }}>
        <strong>Methodik:</strong> ANQ EFM v4+. Isolation/Fixierung/Festhalten mit Start+Ende, Zwangsmedikation mit Zeitpunkt.
        Sichtkontakte ≤30 Min (SAMW/NKVF). Dauer-Warnung: Iso &gt;24h, Iso &gt;72h kritisch, Fix &gt;12h.
        Unterbrechungen ≤2h gelten nicht als Abbruch.
      </div>
    </div>
  );
});

export default EfmReportPanel;
