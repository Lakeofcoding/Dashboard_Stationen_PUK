/**
 * BsclReportPanel.tsx — v1
 *
 * BI-Reporting: BSCL (Erwachsene) + HoNOSCA-SR (KJPP) Selbstbeurteilung.
 * 9 BSCL-Skalen, GSI-basiert, Drill: Klinik → Zentrum → Station
 */
import { useEffect, useState, useMemo, useImperativeHandle, forwardRef } from "react";
import type { ReportPanelHandle } from "./HonosReportPanel";

/* ─── Types ─── */
interface ScatterPoint {
  case_id: string; entry: number; discharge: number; diff: number;
  clinic: string; station: string; center: string; instrument: string;
  admission: string; discharge_date: string | null;
}
interface KPIs {
  total: number; with_entry: number; with_both: number;
  improved: number; same: number; worse: number;
  avg_diff: number | null; avg_entry: number | null; avg_discharge: number | null;
  entry_completion_pct: number; pair_completion_pct: number;
  improved_pct: number; worse_pct: number;
}
interface Subscale { label: string; max: number; avg_entry: number | null; avg_discharge: number | null; avg_diff: number | null; }
interface ClinicRow { clinic: string; n: number; avg_diff: number; improved_pct: number; }
interface StationRow { station: string; clinic: string; center: string; n: number; avg_diff: number; improved_pct: number; }
interface HistBucket { diff: number; count: number; }
interface WorseCase { case_id: string; station: string; clinic: string; center: string; entry: number; discharge: number; diff: number; admission: string; discharge_date: string | null; }
interface Consistency { total_cases: number; bscl_complete: number; completion_pct: number; has_items: boolean; adults_bscl: number; kjpp_honosca_sr: number; }
interface Hierarchy { [clinic: string]: { [center: string]: string[] } }
interface ItemDetail { item: number; label: string; avg_entry: number | null; avg_discharge: number | null; avg_diff: number | null; n: number; }
interface BsclData {
  scatter: ScatterPoint[]; kpis: KPIs;
  subscales: Record<string, Subscale>;
  items_by_scale: Record<string, ItemDetail[]>;
  by_clinic: ClinicRow[]; by_station: StationRow[];
  histogram: HistBucket[]; worse_list: WorseCase[];
  consistency: Consistency; hierarchy: Hierarchy;
}

interface Props { auth: { token: string }; canView: boolean; monat?: string; onMonatChange?: (m: string) => void; }

/* ─── Helpers ─── */
const CC: Record<string, string> = { EPP: "#2563eb", FPP: "#dc2626", APP: "#059669", KJPP: "#d97706" };
const cc = (k: string) => CC[k] ?? "#6b7280";
const fmt = (v: number | null, d = 2) => v == null ? "–" : v.toFixed(d);

/* ─── KPI Card ─── */
function KPI({ label, value, sub, color, unit }: { label: string; value: string; sub?: string; color?: string; unit?: string }) {
  return (
    <div style={{ flex: "1 1 120px", background: "#fff", borderRadius: 12, padding: "12px 14px",
      border: "1px solid #e5e7eb", boxShadow: "0 1px 3px rgba(0,0,0,0.03)" }}>
      <div style={{ fontSize: 10, color: "#9ca3af", marginBottom: 4, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color ?? "#111827", letterSpacing: -0.5 }}>
        {value}{unit && <span style={{ fontSize: 12, fontWeight: 600, marginLeft: 2 }}>{unit}</span>}
      </div>
      {sub && <div style={{ fontSize: 9, color: "#9ca3af", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

/* ═══ MAIN PANEL ═══ */
const BsclReportPanel = forwardRef<ReportPanelHandle, Props>(function BsclReportPanel({ auth, canView, monat, onMonatChange }, ref) {
  const [data, setData] = useState<BsclData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drillClinic, setDrillClinic] = useState<string | null>(null);
  const [drillCenter, setDrillCenter] = useState<string | null>(null);
  const [drillStation, setDrillStation] = useState<string | null>(null);
  const [hov, setHov] = useState<ScatterPoint | null>(null);
  const [wSort, setWSort] = useState<"diff" | "case_id" | "station">("diff");
  const [expandedScales, setExpandedScales] = useState<Set<string>>(new Set());

  useImperativeHandle(ref, () => ({
    canGoBack: () => !!(drillStation || drillCenter || drillClinic),
    goBack: () => {
      if (drillStation) setDrillStation(null);
      else if (drillCenter) setDrillCenter(null);
      else if (drillClinic) setDrillClinic(null);
    },
  }), [drillClinic, drillCenter, drillStation]);

  const fClinic = drillClinic || "", fCenter = drillCenter || "", fStation = drillStation || "";

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams();
    if (fClinic) p.set("clinic", fClinic); if (fCenter) p.set("center", fCenter); if (fStation) p.set("station", fStation);
    if (monat) p.set("monat", monat);
    fetch(`/api/reporting/bscl?${p}`, { headers: { Authorization: `Bearer ${auth.token}` } })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setData(d); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [fClinic, fCenter, fStation, auth.token, monat]);

  if (!canView) return <div style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>Keine Berechtigung.</div>;
  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "#9ca3af" }}>Lade BSCL-Daten…</div>;
  if (error) return <div style={{ padding: 40, textAlign: "center", color: "#dc2626" }}>Fehler: {error}</div>;
  if (!data) return null;

  const { kpis, scatter, subscales, items_by_scale, by_clinic, by_station, histogram, worse_list, consistency, hierarchy } = data;
  const clinicKeys = Object.keys(hierarchy).sort();
  const scaleKeys = Object.keys(subscales);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <h2 style={{ margin: "0 0 4px", fontSize: 18, fontWeight: 700, color: "#111827" }}>
        📊 BSCL / HoNOSCA-SR Reporting <span style={{ fontSize: 12, fontWeight: 400, color: "#9ca3af" }}>Selbstbeurteilung</span>
      </h2>
      <p style={{ margin: "0 0 16px", fontSize: 11, color: "#9ca3af" }}>
        BSCL: 53 Items, 9 Skalen, GSI 0–4 (Erwachsene) · HoNOSCA-SR: 13 Items (KJPP) ·
        Positive Δ = Verbesserung (Symptomreduktion)
      </p>

      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 14, fontSize: 13, color: "#6b7280" }}>
        <span onClick={() => { setDrillClinic(null); setDrillCenter(null); setDrillStation(null); }}
          style={{ cursor: "pointer", fontWeight: !drillClinic ? 700 : 400, color: !drillClinic ? "#7c3aed" : "#6b7280" }}>Alle Kliniken</span>
        {drillClinic && <><span style={{ color: "#d1d5db" }}>/</span>
          <span onClick={() => { setDrillCenter(null); setDrillStation(null); }}
            style={{ cursor: "pointer", fontWeight: !drillCenter ? 700 : 400, color: !drillCenter ? "#7c3aed" : "#6b7280" }}>{drillClinic}</span></>}
        {drillCenter && <><span style={{ color: "#d1d5db" }}>/</span>
          <span onClick={() => setDrillStation(null)}
            style={{ cursor: "pointer", fontWeight: !drillStation ? 700 : 400, color: !drillStation ? "#7c3aed" : "#6b7280" }}>{drillCenter}</span></>}
        {drillStation && <><span style={{ color: "#d1d5db" }}>/</span><span style={{ fontWeight: 700, color: "#7c3aed" }}>{drillStation}</span></>}
      </div>

      {/* Drill Tiles */}
      {!drillClinic && clinicKeys.length > 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(220px,1fr))", gap: 12, marginBottom: 18 }}>
          {clinicKeys.map(k => { const cd = by_clinic.find(c => c.clinic === k); return (
            <div key={k} onClick={() => setDrillClinic(k)}
              style={{ padding: "14px 16px", borderRadius: 12, cursor: "pointer", transition: "all .15s",
                background: "#fff", border: `2px solid ${cc(k)}30`, boxShadow: "0 1px 4px rgba(0,0,0,.04)" }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = cc(k); }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = cc(k) + "30"; }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: cc(k) }} />
                <span style={{ fontWeight: 700, fontSize: 14 }}>{k}</span>
              </div>
              {cd && <div style={{ fontSize: 11, color: "#6b7280" }}>n={cd.n} · Ø Δ GSI={fmt(cd.avg_diff)} · {cd.improved_pct}% verbessert</div>}
            </div>
          ); })}
        </div>
      )}
      {drillClinic && !drillCenter && hierarchy[drillClinic] && Object.keys(hierarchy[drillClinic]).length > 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 10, marginBottom: 16 }}>
          {Object.keys(hierarchy[drillClinic]).sort().map(ctr => (
            <div key={ctr} onClick={() => setDrillCenter(ctr)}
              style={{ padding: "10px 14px", borderRadius: 10, cursor: "pointer", background: "#fff",
                border: "1px solid #e5e7eb", fontSize: 13 }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = "#7c3aed"; }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = "#e5e7eb"; }}>
              <strong>{ctr}</strong>
              <div style={{ fontSize: 10, color: "#9ca3af" }}>{hierarchy[drillClinic][ctr].length} Stationen</div>
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
                {sd && <div style={{ fontSize: 10, color: "#9ca3af" }}>n={sd.n} · Ø Δ={fmt(sd.avg_diff)}</div>}
              </div>
            );
          })}
        </div>
      )}

      {/* KPI Cards */}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 18 }}>
        <KPI label="Fälle gesamt" value={String(kpis.total)} />
        <KPI label="Ø GSI Eintritt" value={fmt(kpis.avg_entry)} color="#7c3aed" />
        <KPI label="Ø GSI Austritt" value={fmt(kpis.avg_discharge)} color="#2563eb" />
        <KPI label="Ø Δ GSI" value={fmt(kpis.avg_diff)} color={kpis.avg_diff != null && kpis.avg_diff > 0 ? "#059669" : "#dc2626"} />
        <KPI label="Verbessert" value={`${kpis.improved_pct}`} unit="%" color="#059669" sub={`${kpis.improved}/${kpis.with_both}`} />
        <KPI label="Verschlechtert" value={`${kpis.worse_pct}`} unit="%" color="#dc2626" sub={`${kpis.worse}/${kpis.with_both}`} />
        <KPI label="Erfassungsrate" value={`${kpis.entry_completion_pct}`} unit="%" sub={`ET: ${kpis.with_entry}/${kpis.total}`} />
      </div>

      {/* ─── BSCL 9-Skalen Grouped Bar Chart (klickbar) ─── */}
      {scaleKeys.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 14, fontWeight: 700 }}>BSCL Skalen (Ø pro Skala, 0–4)</h3>
          <p style={{ margin: "0 0 12px", fontSize: 10, color: "#9ca3af" }}>Skala anklicken für Einzelitems</p>
          <div style={{ display: "flex", alignItems: "end", gap: 6, height: 180, paddingBottom: 24, position: "relative" }}>
            {scaleKeys.map(k => {
              const s = subscales[k];
              if (!s) return null;
              const eH = s.avg_entry != null ? (s.avg_entry / 4) * 150 : 0;
              const dH = s.avg_discharge != null ? (s.avg_discharge / 4) * 150 : 0;
              const diff = s.avg_diff;
              const isOpen = expandedScales.has(k);
              return (
                <div key={k} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 2, cursor: "pointer" }}
                  onClick={() => setExpandedScales(prev => {
                    const next = new Set(prev);
                    if (next.has(k)) next.delete(k); else next.add(k);
                    return next;
                  })}>
                  <div style={{ fontSize: 8, color: diff != null && diff > 0 ? "#059669" : diff != null && diff < 0 ? "#dc2626" : "#9ca3af", fontWeight: 700 }}>
                    {diff != null ? (diff > 0 ? "+" : "") + diff.toFixed(2) : "–"}
                  </div>
                  <div style={{ display: "flex", gap: 2, alignItems: "end", height: 150 }}>
                    <div style={{ width: 16, height: eH, background: "#7c3aed", borderRadius: "3px 3px 0 0", transition: "height .3s",
                      opacity: isOpen ? 1 : 0.7 }}
                      title={`ET: ${fmt(s.avg_entry)}`} />
                    <div style={{ width: 16, height: dH, background: "#2563eb", borderRadius: "3px 3px 0 0", transition: "height .3s",
                      opacity: isOpen ? 1 : 0.7 }}
                      title={`AT: ${fmt(s.avg_discharge)}`} />
                  </div>
                  <div style={{ fontSize: 8, color: isOpen ? "#7c3aed" : "#6b7280", fontWeight: isOpen ? 700 : 400,
                    textAlign: "center", lineHeight: 1.2, marginTop: 2, maxWidth: 60 }}>
                    {s.label.length > 12 ? s.label.slice(0, 11) + "…" : s.label}
                  </div>
                  <div style={{ fontSize: 8, color: isOpen ? "#7c3aed" : "#d1d5db" }}>{isOpen ? "▲" : "▼"}</div>
                </div>
              );
            })}
          </div>
          <div style={{ display: "flex", gap: 16, justifyContent: "center", fontSize: 10, color: "#6b7280", marginBottom: 8 }}>
            <span><span style={{ display: "inline-block", width: 10, height: 10, background: "#7c3aed", borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />Eintritt</span>
            <span><span style={{ display: "inline-block", width: 10, height: 10, background: "#2563eb", borderRadius: 2, marginRight: 4, verticalAlign: "middle" }} />Austritt</span>
          </div>

          {/* ─── Aufklappbare Item-Details pro Skala ─── */}
          {scaleKeys.filter(k => expandedScales.has(k)).map(k => {
            const items = items_by_scale?.[k] || [];
            const s = subscales[k];
            if (!items.length) return null;
            return (
              <div key={`detail-${k}`} style={{ marginTop: 8, padding: "10px 12px", borderRadius: 8,
                background: "#faf5ff", border: "1px solid #e9d5ff", animation: "fadeIn .2s" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#7c3aed" }}>
                    {s?.label} ({items.length} Items)
                  </span>
                  <button onClick={(e) => { e.stopPropagation(); setExpandedScales(prev => { const n = new Set(prev); n.delete(k); return n; }); }}
                    style={{ background: "none", border: "none", cursor: "pointer", fontSize: 11, color: "#9ca3af" }}>✕ schliessen</button>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "32px 1fr 60px 60px 60px", gap: "1px", fontSize: 10 }}>
                  <div style={{ padding: "3px 4px", fontWeight: 700, color: "#6b7280" }}>#</div>
                  <div style={{ padding: "3px 4px", fontWeight: 700, color: "#6b7280" }}>Item</div>
                  <div style={{ padding: "3px 4px", fontWeight: 700, color: "#6b7280", textAlign: "center" }}>Ø ET</div>
                  <div style={{ padding: "3px 4px", fontWeight: 700, color: "#6b7280", textAlign: "center" }}>Ø AT</div>
                  <div style={{ padding: "3px 4px", fontWeight: 700, color: "#6b7280", textAlign: "center" }}>Δ</div>
                  {items.map(it => {
                    const diffColor = it.avg_diff != null ? (it.avg_diff > 0.05 ? "#059669" : it.avg_diff < -0.05 ? "#dc2626" : "#6b7280") : "#d1d5db";
                    return [
                      <div key={`n${it.item}`} style={{ padding: "3px 4px", color: "#9ca3af", fontFamily: "monospace" }}>{it.item}</div>,
                      <div key={`l${it.item}`} style={{ padding: "3px 4px", color: "#374151", lineHeight: 1.3 }}>
                        {it.label.length > 55 ? it.label.slice(0, 52) + "…" : it.label}
                        {it.n > 0 && <span style={{ color: "#d1d5db", fontSize: 9, marginLeft: 4 }}>n={it.n}</span>}
                      </div>,
                      <div key={`e${it.item}`} style={{ padding: "3px 4px", textAlign: "center", color: "#7c3aed" }}>{fmt(it.avg_entry)}</div>,
                      <div key={`d${it.item}`} style={{ padding: "3px 4px", textAlign: "center", color: "#2563eb" }}>{fmt(it.avg_discharge)}</div>,
                      <div key={`x${it.item}`} style={{ padding: "3px 4px", textAlign: "center", color: diffColor, fontWeight: 600 }}>
                        {it.avg_diff != null ? (it.avg_diff > 0 ? "+" : "") + it.avg_diff.toFixed(2) : "–"}
                      </div>,
                    ];
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ─── Scatter Plot (GSI ET vs AT) ─── */}
      {scatter.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700 }}>GSI: Eintritt vs. Austritt</h3>
          <div style={{ position: "relative", height: 260, margin: "0 auto", maxWidth: 500 }}>
            <svg viewBox="0 0 300 260" style={{ width: "100%", height: "100%" }}>
              <line x1="40" y1="10" x2="40" y2="230" stroke="#e5e7eb" />
              <line x1="40" y1="230" x2="290" y2="230" stroke="#e5e7eb" />
              <line x1="40" y1="230" x2="290" y2="10" stroke="#d1d5db" strokeDasharray="4" />
              {[0, 1, 2, 3, 4].map(v => (
                <g key={v}>
                  <text x="36" y={230 - (v / 4) * 220 + 4} textAnchor="end" fontSize="8" fill="#9ca3af">{v}</text>
                  <text x={40 + (v / 4) * 250} y="244" textAnchor="middle" fontSize="8" fill="#9ca3af">{v}</text>
                </g>
              ))}
              <text x="165" y="258" textAnchor="middle" fontSize="9" fill="#6b7280">GSI Eintritt</text>
              <text x="12" y="120" textAnchor="middle" fontSize="9" fill="#6b7280" transform="rotate(-90,12,120)">GSI Austritt</text>
              {scatter.map((p, i) => {
                const cx = 40 + (p.entry / 4) * 250;
                const cy = 230 - (p.discharge / 4) * 220;
                return (
                  <circle key={i} cx={cx} cy={cy} r={4}
                    fill={cc(p.clinic)} opacity={0.6} stroke="#fff" strokeWidth={0.5}
                    style={{ cursor: "pointer" }}
                    onMouseEnter={() => setHov(p)} onMouseLeave={() => setHov(null)} />
                );
              })}
            </svg>
            {hov && (
              <div style={{ position: "absolute", top: 10, right: 10, background: "#fff", border: "1px solid #e5e7eb",
                borderRadius: 8, padding: "8px 12px", fontSize: 11, boxShadow: "0 2px 8px rgba(0,0,0,.1)", pointerEvents: "none" }}>
                <strong>{hov.case_id}</strong> ({hov.instrument})<br />
                GSI: {fmt(hov.entry)} → {fmt(hov.discharge)} (Δ {hov.diff > 0 ? "+" : ""}{fmt(hov.diff)})<br />
                <span style={{ color: "#9ca3af" }}>{hov.station} · {hov.clinic}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── Histogram ─── */}
      {histogram.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #e5e7eb", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700 }}>Verteilung Δ GSI</h3>
          <div style={{ display: "flex", alignItems: "end", gap: 1, height: 100 }}>
            {histogram.map((b, i) => {
              const maxC = Math.max(...histogram.map(h => h.count));
              const h = maxC > 0 ? (b.count / maxC) * 80 : 0;
              return (
                <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div style={{ fontSize: 7, color: "#9ca3af" }}>{b.count > 0 ? b.count : ""}</div>
                  <div style={{ width: "100%", height: h, background: b.diff >= 0 ? "#86efac" : "#fca5a5",
                    borderRadius: "2px 2px 0 0", minWidth: 4 }} />
                  <div style={{ fontSize: 6, color: "#9ca3af", marginTop: 1 }}>{b.diff.toFixed(1)}</div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 9, color: "#9ca3af", textAlign: "center", marginTop: 4 }}>← Verschlechterung | Verbesserung →</div>
        </div>
      )}

      {/* ─── Verschlechterungsliste ─── */}
      {worse_list.length > 0 && (
        <div style={{ background: "#fff", borderRadius: 12, border: "1px solid #fecaca", padding: 16, marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 700, color: "#dc2626" }}>
            ⚠ Verschlechterungsliste ({worse_list.length})
          </h3>
          <div style={{ display: "flex", gap: 8, marginBottom: 8, fontSize: 10 }}>
            {(["diff", "case_id", "station"] as const).map(k => (
              <button key={k} onClick={() => setWSort(k)}
                style={{ padding: "2px 8px", borderRadius: 4, fontSize: 10, border: wSort === k ? "1px solid #7c3aed" : "1px solid #e5e7eb",
                  background: wSort === k ? "#f5f3ff" : "#fff", color: wSort === k ? "#7c3aed" : "#6b7280", cursor: "pointer" }}>
                {k === "diff" ? "Δ GSI" : k === "case_id" ? "Fall-Nr" : "Station"}
              </button>
            ))}
          </div>
          <div style={{ maxHeight: 200, overflowY: "auto" }}>
            <table style={{ width: "100%", fontSize: 11, borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid #e5e7eb" }}>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "#6b7280", fontWeight: 600 }}>Fall</th>
                  <th style={{ textAlign: "left", padding: "4px 8px", color: "#6b7280", fontWeight: 600 }}>Station</th>
                  <th style={{ textAlign: "right", padding: "4px 8px", color: "#6b7280", fontWeight: 600 }}>GSI ET</th>
                  <th style={{ textAlign: "right", padding: "4px 8px", color: "#6b7280", fontWeight: 600 }}>GSI AT</th>
                  <th style={{ textAlign: "right", padding: "4px 8px", color: "#dc2626", fontWeight: 600 }}>Δ GSI</th>
                </tr>
              </thead>
              <tbody>
                {[...worse_list].sort((a, b) => wSort === "diff" ? a.diff - b.diff : wSort === "case_id" ? a.case_id.localeCompare(b.case_id) : a.station.localeCompare(b.station))
                  .map((w, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      <td style={{ padding: "4px 8px", fontFamily: "monospace", fontSize: 10 }}>{w.case_id}</td>
                      <td style={{ padding: "4px 8px" }}>{w.station}</td>
                      <td style={{ padding: "4px 8px", textAlign: "right" }}>{fmt(w.entry)}</td>
                      <td style={{ padding: "4px 8px", textAlign: "right" }}>{fmt(w.discharge)}</td>
                      <td style={{ padding: "4px 8px", textAlign: "right", color: "#dc2626", fontWeight: 700 }}>{fmt(w.diff)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Konsistenz */}
      <div style={{ background: "#f5f3ff", borderRadius: 10, padding: "10px 14px", marginBottom: 14, fontSize: 11, color: "#6b7280", border: "1px solid #ddd6fe" }}>
        <strong style={{ color: "#7c3aed" }}>Datenqualität:</strong>{" "}
        {consistency.completion_pct}% Erfassungsrate ({consistency.bscl_complete}/{consistency.total_cases}) ·{" "}
        {consistency.adults_bscl} BSCL (Erw.) · {consistency.kjpp_honosca_sr} HoNOSCA-SR (KJPP)
        {consistency.has_items && <span style={{ marginLeft: 8, color: "#059669" }}>✓ Einzelitems vorhanden</span>}
      </div>

      {/* Methodik */}
      <div style={{ padding: "8px 12px", borderRadius: 8, background: "#f9fafb", border: "1px solid #e5e7eb", fontSize: 9, color: "#9ca3af", lineHeight: 1.5 }}>
        <strong style={{ color: "#6b7280" }}>Methodik:</strong> BSCL 53 Items, 9 Skalen (Franke 2000, ANQ), GSI = Mittelwert aller Items (0–4).
        HoNOSCA-SR 13 Items, Selbstbeurteilung KJPP. Verbesserung = positives Δ GSI.
      </div>
    </div>
  );
});
export default BsclReportPanel;
