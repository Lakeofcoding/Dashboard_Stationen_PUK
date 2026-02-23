/**
 * MonitoringPanel – Klinische Verlaufs-Charts pro Fall.
 *
 * Zeigt bei Klick auf einen Fall echte SVG-Linien-Charts:
 * - Neutrophile (Grenzwert 2.0 / 1.5 G/l)
 * - QTc-Verlauf (Grenzwert 480 / 500 ms)
 * - Clozapin-Spiegel (Therapeutischer Bereich)
 * - Troponin (erste Wochen)
 * - Leberwerte ALAT/ASAT
 *
 * Daten kommen live aus /api/cases/{id}/lab-history und /ekg-history.
 */
import React, { useState, useEffect, useMemo, useCallback } from "react";
import type { CaseSummary, ParameterStatus, LabMeasurement, EkgMeasurement } from "./types";

/* ───── API ───── */
const API = "";
async function fetchJson<T>(url: string, station: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${url}?ctx=${encodeURIComponent(station)}`, { credentials: "include" });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

/* ───── Farben ───── */
const C = {
  ok: "#22c55e", warn: "#f59e0b", critical: "#ef4444", na: "#d1d5db",
  blue: "#3b82f6", indigo: "#6366f1", teal: "#14b8a6", rose: "#f43f5e",
  orange: "#f97316",
  grid: "#e5e7eb", gridLight: "#f3f4f6", text: "#6b7280", textDark: "#374151",
  bg: "#fff", bgAlt: "#f9fafb",
};

const MONITORING_IDS = ["ekg", "clozapin", "suicidality", "isolation"];

/* ═══════════════════════════════════════════ */
/* Main                                        */
/* ═══════════════════════════════════════════ */
interface Props { cases: CaseSummary[]; selectedCaseId: string | null; onSelectCase: (id: string) => void; }

export default function MonitoringPanel({ cases, selectedCaseId, onSelectCase }: Props) {
  const [expandedCase, setExpandedCase] = useState<string | null>(null);
  const [labData, setLabData] = useState<LabMeasurement[]>([]);
  const [ekgData, setEkgData] = useState<EkgMeasurement[]>([]);
  const [loading, setLoading] = useState(false);

  const monitoredCases = useMemo(() =>
    cases.filter(c => (c.parameter_status ?? []).some(p => MONITORING_IDS.includes(p.id))),
    [cases]);

  const activeCaseId = expandedCase ?? selectedCaseId;
  const activeCase = useMemo(() => monitoredCases.find(c => c.case_id === activeCaseId), [monitoredCases, activeCaseId]);

  // Stabile Referenz-Werte fuer useEffect (verhindert Re-Fetch bei Polling)
  const activeStationId = activeCase?.station_id;

  const fetchHistory = useCallback(async (cid: string, station: string) => {
    setLoading(true);
    const [lab, ekg] = await Promise.all([
      fetchJson<{ lab_history: LabMeasurement[] }>(`/api/cases/${cid}/lab-history`, station),
      fetchJson<{ ekg_history: EkgMeasurement[] }>(`/api/cases/${cid}/ekg-history`, station),
    ]);
    setLabData(lab?.lab_history ?? []);
    setEkgData(ekg?.ekg_history ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (activeCaseId && activeStationId) fetchHistory(activeCaseId, activeStationId);
    else { setLabData([]); setEkgData([]); }
    // Nur re-fetchen wenn sich die *ID* aendert, nicht die Objekt-Referenz
  }, [activeCaseId, activeStationId, fetchHistory]);

  return (
    <div>
      <h3 style={{ margin: "0 0 6px 0", fontSize: "1.1rem" }}>Klinisches Monitoring</h3>
      <p style={{ margin: "0 0 16px 0", fontSize: 12, color: C.text }}>
        Übersicht aktiver Monitoring-Parameter. Klick auf einen Fall für Verlaufs-Charts.
      </p>

      {monitoredCases.length === 0 ? (
        <div style={{ padding: 24, color: "#9ca3af", textAlign: "center", background: C.bgAlt, borderRadius: 8 }}>
          Keine Fälle mit aktivem Monitoring.
        </div>
      ) : (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {/* Left: case list */}
          <div style={{ flex: "0 0 400px", maxHeight: 540, overflowY: "auto" }}>
            {monitoredCases.map(c => (
              <CaseRow key={c.case_id} c={c} isActive={activeCaseId === c.case_id}
                onClick={() => { setExpandedCase(expandedCase === c.case_id ? null : c.case_id); onSelectCase(c.case_id); }} />
            ))}
          </div>

          {/* Right: charts */}
          <div style={{ flex: 1, minWidth: 360 }}>
            {activeCase ? (
              <div style={{ background: C.bg, border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
                  Fall {activeCase.case_id}
                  <span style={{ fontWeight: 400, fontSize: 12, color: C.text, marginLeft: 8 }}>
                    {activeCase.station_id} · {activeCase.clinic}
                  </span>
                </div>
                {loading ? (
                  <div style={{ padding: 32, textAlign: "center", color: C.text }}>Lade Verlaufsdaten…</div>
                ) : (
                  <ChartPanel lab={labData} ekg={ekgData} params={activeCase.parameter_status ?? []} />
                )}
              </div>
            ) : (
              <div style={{ padding: 32, textAlign: "center", color: "#9ca3af", background: C.bgAlt, borderRadius: 8 }}>
                Wählen Sie einen Fall für Verlaufs-Charts.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════ */
/* Case row                                    */
/* ═══════════════════════════════════════════ */
function CaseRow({ c, isActive, onClick }: { c: CaseSummary; isActive: boolean; onClick: () => void }) {
  const params = c.parameter_status ?? [];
  const icons: Record<string, string> = { ekg: "💓", clozapin: "💊", suicidality: "⚠", isolation: "🔒" };
  return (
    <div onClick={onClick} style={{
      padding: "10px 12px", borderRadius: 8, marginBottom: 6, cursor: "pointer",
      background: isActive ? "#eff6ff" : C.bg,
      border: `1px solid ${isActive ? "#93c5fd" : "#e5e7eb"}`, transition: "all 0.15s",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span style={{ fontWeight: 700, fontFamily: "monospace", fontSize: 13 }}>{c.case_id}</span>
          <span style={{ fontSize: 11, color: C.text, marginLeft: 8 }}>{c.station_id}</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {MONITORING_IDS.map(id => {
            const p = params.find(x => x.id === id);
            if (!p) return null;
            const col = p.status === "critical" ? C.critical : p.status === "warn" ? C.warn : p.status === "ok" ? C.ok : C.na;
            return (
              <span key={id} title={`${p.label}: ${p.detail ?? "–"}`} style={{
                fontSize: 10, padding: "1px 5px", borderRadius: 3, fontWeight: 600,
                background: `${col}18`, color: col, border: `1px solid ${col}44`,
              }}>{icons[id]} {p.label}</span>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════ */
/* Chart panel                                 */
/* ═══════════════════════════════════════════ */
function ChartPanel({ lab, ekg, params }: { lab: LabMeasurement[]; ekg: EkgMeasurement[]; params: ParameterStatus[] }) {
  const hasClozapin = params.some(p => p.id === "clozapin");
  const hasLab = lab.length > 1;
  const hasEkg = ekg.length > 1;

  if (!hasLab && !hasEkg) {
    return (
      <div style={{ padding: 20, textAlign: "center", color: C.text, fontSize: 12 }}>
        Keine Verlaufsdaten für diesen Fall vorhanden.
        {hasClozapin && " Clozapin aktiv, aber noch keine Labordaten."}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 12 }}>
      {hasLab && <TrendChart title="Neutrophile abs." unit="G/l" data={lab} vKey="neutro" color={C.blue}
        thresholds={[{ v: 2.0, c: C.warn, l: "2.0 Grenzwert" }, { v: 1.5, c: C.critical, l: "1.5 Kritisch" }]}
        yRange={[0, 8]} direction="lower-bad" />}

      {hasEkg && <TrendChart title="QTc" unit="ms" data={ekg} vKey="qtc" color={C.indigo}
        thresholds={[{ v: 480, c: C.warn, l: "480 Warnung" }, { v: 500, c: C.critical, l: "500 Alarm" }]}
        yRange={[350, 560]} direction="upper-bad" />}

      {hasLab && lab.some(m => m.cloz_spiegel != null) &&
        <TrendChart title="Clozapin-Spiegel" unit="ng/ml" data={lab} vKey="cloz_spiegel" color={C.teal}
          thresholds={[{ v: 350, c: C.ok, l: "350 Therap.min" }, { v: 600, c: C.warn, l: "600 Obere Gr." }]}
          yRange={[0, 1100]} direction="upper-bad" />}

      {hasLab && lab.some(m => m.troponin != null) &&
        <TrendChart title="Troponin T hs" unit="ng/l" data={lab} vKey="troponin" color={C.rose}
          thresholds={[{ v: 14, c: C.critical, l: "14 Referenz" }]}
          yRange={[0, 80]} direction="upper-bad" />}

      {hasLab && lab.some(m => m.alat != null) &&
        <DualTrendChart title="Leberwerte" data={lab}
          series={[{ key: "alat", label: "ALAT", color: C.orange }, { key: "asat", label: "ASAT", color: C.teal }]}
          unit="U/l" thresholds={[{ v: 50, c: C.warn, l: "50 Referenz" }]} yRange={[0, 130]} />}

      {hasEkg && <TrendChart title="Herzfrequenz" unit="bpm" data={ekg} vKey="hr" color={C.ok}
        thresholds={[{ v: 60, c: C.na, l: "60 Bradyk." }, { v: 100, c: C.warn, l: "100 Tachyk." }]}
        yRange={[40, 130]} direction="upper-bad" />}
    </div>
  );
}

/* ═══════════════════════════════════════════ */
/* SVG Trend Chart                             */
/* ═══════════════════════════════════════════ */
const W = 520, H = 160;
const P = { t: 20, r: 14, b: 28, l: 44 };
const PW = W - P.l - P.r, PH = H - P.t - P.b;

interface TH { v: number; c: string; l: string; }

function TrendChart({ title, unit, data, vKey, color, thresholds = [], yRange, direction = "upper-bad" }: {
  title: string; unit: string;
  data: Record<string, unknown>[]; vKey: string; color: string;
  thresholds?: TH[]; yRange: [number, number]; direction?: "upper-bad" | "lower-bad";
}) {
  const pts = useMemo(() =>
    data.map(d => ({ dt: d.date as string, v: d[vKey] as number | null }))
        .filter(p => p.v != null) as { dt: string; v: number }[],
    [data, vKey]);

  if (pts.length < 2) return null;

  const [lo, hi] = yRange;
  const rng = hi - lo || 1;
  const toX = (i: number) => P.l + (i / (pts.length - 1)) * PW;
  const toY = (v: number) => P.t + PH - ((Math.min(Math.max(v, lo), hi) - lo) / rng) * PH;

  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p.v).toFixed(1)}`).join(" ");
  const nTicks = 4;
  const ticks = Array.from({ length: nTicks + 1 }, (_, i) => lo + (rng * i) / nTicks);

  const last = pts[pts.length - 1];
  const lastSt = ptStatus(last.v, thresholds, direction);

  const xLabels = spreadLabels(pts, 5);

  return (
    <div style={{ background: C.bgAlt, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: C.textDark }}>{title}</span>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: "1px 6px", borderRadius: 4,
          color: lastSt === "critical" ? C.critical : lastSt === "warn" ? C.warn : C.ok,
          background: `${lastSt === "critical" ? C.critical : lastSt === "warn" ? C.warn : C.ok}15`,
        }}>
          Aktuell: {last.v} {unit}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>
        {/* Axes */}
        <line x1={P.l} x2={P.l} y1={P.t} y2={H - P.b} stroke={C.grid} />
        <line x1={P.l} x2={W - P.r} y1={H - P.b} y2={H - P.b} stroke={C.grid} />
        {/* Grid + Y labels */}
        {ticks.map((v, i) => <g key={i}>
          <line x1={P.l} x2={W - P.r} y1={toY(v)} y2={toY(v)} stroke={C.gridLight} />
          <text x={P.l - 4} y={toY(v) + 3} textAnchor="end" fontSize={9} fill={C.text}>
            {v % 1 === 0 ? v : v.toFixed(1)}
          </text>
        </g>)}
        {/* Thresholds */}
        {thresholds.map((t, i) => <g key={`th${i}`}>
          <line x1={P.l} x2={W - P.r} y1={toY(t.v)} y2={toY(t.v)}
            stroke={t.c} strokeWidth={1.5} strokeDasharray="6 3" opacity={0.65} />
          <text x={W - P.r - 2} y={toY(t.v) - 3} textAnchor="end" fontSize={8} fill={t.c} fontWeight={600}>{t.l}</text>
        </g>)}
        {/* Line */}
        <path d={path} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
        {/* Points */}
        {pts.map((p, i) => {
          const st = ptStatus(p.v, thresholds, direction);
          const fc = st === "critical" ? C.critical : st === "warn" ? C.warn : color;
          return <circle key={i} cx={toX(i)} cy={toY(p.v)} r={3} fill={fc} stroke={C.bg} strokeWidth={1.5}>
            <title>{fmtDate(p.dt)}: {p.v} {unit}</title>
          </circle>;
        })}
        {/* X labels */}
        {xLabels.map(({ i, l }) => <text key={i} x={toX(i)} y={H - 5} textAnchor="middle" fontSize={8} fill={C.text}>{l}</text>)}
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════ */
/* Dual Trend Chart (ALAT + ASAT)              */
/* ═══════════════════════════════════════════ */
function DualTrendChart({ title, data, series, unit, thresholds = [], yRange }: {
  title: string; data: Record<string, unknown>[];
  series: { key: string; label: string; color: string }[];
  unit: string; thresholds?: TH[]; yRange: [number, number];
}) {
  const allSeries = useMemo(() => series.map(s => ({
    ...s,
    pts: data.map(d => ({ dt: d.date as string, v: d[s.key] as number | null }))
             .filter(p => p.v != null) as { dt: string; v: number }[],
  })), [data, series]);

  if (allSeries.every(s => s.pts.length < 2)) return null;

  const [lo, hi] = yRange;
  const rng = hi - lo || 1;
  const ticks = Array.from({ length: 5 }, (_, i) => lo + (rng * i) / 4);

  return (
    <div style={{ background: C.bgAlt, borderRadius: 8, padding: "10px 12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: C.textDark }}>{title}</span>
        <div style={{ display: "flex", gap: 10 }}>
          {series.map(s => <span key={s.key} style={{ fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}>
            <span style={{ width: 8, height: 3, background: s.color, borderRadius: 1, display: "inline-block" }} />
            {s.label}
          </span>)}
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }}>
        <line x1={P.l} x2={P.l} y1={P.t} y2={H - P.b} stroke={C.grid} />
        <line x1={P.l} x2={W - P.r} y1={H - P.b} y2={H - P.b} stroke={C.grid} />
        {ticks.map((v, i) => <g key={i}>
          <line x1={P.l} x2={W - P.r} y1={P.t + PH - ((v - lo) / rng) * PH} y2={P.t + PH - ((v - lo) / rng) * PH} stroke={C.gridLight} />
          <text x={P.l - 4} y={P.t + PH - ((v - lo) / rng) * PH + 3} textAnchor="end" fontSize={9} fill={C.text}>{Math.round(v)}</text>
        </g>)}
        {thresholds.map((t, i) => <line key={`th${i}`} x1={P.l} x2={W - P.r}
          y1={P.t + PH - ((t.v - lo) / rng) * PH} y2={P.t + PH - ((t.v - lo) / rng) * PH}
          stroke={t.c} strokeWidth={1.5} strokeDasharray="6 3" opacity={0.65} />)}
        {allSeries.map(s => {
          if (s.pts.length < 2) return null;
          const toX = (i: number) => P.l + (i / (s.pts.length - 1)) * PW;
          const toY = (v: number) => P.t + PH - ((Math.min(Math.max(v, lo), hi) - lo) / rng) * PH;
          const path = s.pts.map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p.v).toFixed(1)}`).join(" ");
          return <g key={s.key}>
            <path d={path} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" />
            {s.pts.map((p, i) => <circle key={i} cx={toX(i)} cy={toY(p.v)} r={2.5} fill={s.color} stroke={C.bg} strokeWidth={1}>
              <title>{s.label}: {p.v} {unit} ({fmtDate(p.dt)})</title>
            </circle>)}
          </g>;
        })}
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════ */
/* Helpers                                     */
/* ═══════════════════════════════════════════ */
function ptStatus(v: number, ths: TH[], dir: "upper-bad" | "lower-bad"): string {
  // Sort by severity (critical color first)
  const sorted = [...ths].sort((a, b) => (a.c === C.critical ? -1 : b.c === C.critical ? 1 : 0));
  for (const t of sorted) {
    if (dir === "lower-bad") {
      if (v <= t.v && t.c === C.critical) return "critical";
      if (v <= t.v && t.c === C.warn) return "warn";
    } else {
      if (v >= t.v && t.c === C.critical) return "critical";
      if (v >= t.v && t.c === C.warn) return "warn";
    }
  }
  return "ok";
}

function spreadLabels(pts: { dt: string }[], max: number) {
  if (pts.length <= max) return pts.map((p, i) => ({ i, l: fmtDate(p.dt) }));
  const step = Math.ceil(pts.length / max);
  const r: { i: number; l: string }[] = [];
  for (let i = 0; i < pts.length; i += step) r.push({ i, l: fmtDate(pts[i].dt) });
  const last = pts.length - 1;
  if (!r.some(x => x.i === last)) r.push({ i: last, l: fmtDate(pts[last].dt) });
  return r;
}

function fmtDate(iso: string): string {
  try { const d = new Date(iso); return `${d.getDate()}.${d.getMonth() + 1}.`; }
  catch { return iso.slice(5, 10); }
}
