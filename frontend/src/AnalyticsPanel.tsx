/**
 * AnalyticsPanel — BI-Auswertung für Direktion / Übersicht
 */
import { useMemo, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────
export type CompletenessQuota = {
  key: string; label: string;
  applies_open: boolean; applies_closed: boolean;
  open_filled: number; open_total: number; open_pct: number | null;
  closed_filled: number; closed_total: number; closed_pct: number | null;
};
export type RuleHit = {
  rule_id: string; count: number; message: string;
  category: string; severity: "WARN" | "CRITICAL";
};
export type DocReports = {
  done: number; within_time: number; overdue: number;
  overdue_by_person: { person: string; count: number }[];
};
export type StationAnalytics = {
  station_id: string; center: string; clinic: string;
  total_cases: number; open_cases: number; closed_cases: number;
  completeness_dist: { complete: number; incomplete: number };
  doc_reports: DocReports;
  ack_this_month: { ack_count: number; shift_count: number };
  completeness_quotas: CompletenessQuota[];
  top_rules: RuleHit[];
};
type Props = { stations: StationAnalytics[]; scopeLabel: string };

// ── Farben ───────────────────────────────────────────────────────────
const C = {
  complete: "#22c55e", completeBg: "#f0fdf4",
  incomplete: "#ef4444", incompleteBg: "#fef2f2",
  warn: "#f59e0b", warnBg: "#fffbeb",
  ack: "#3b82f6", shift: "#8b5cf6",
  muted: "#94a3b8", text: "#1e293b", textSec: "#64748b",
  border: "#e2e8f0", white: "#ffffff",
};

// ── Donut-Chart ──────────────────────────────────────────────────────
function Donut({ data, centerLabel, centerSub, size = 140 }: {
  data: { label: string; value: number; color: string }[];
  centerLabel: string; centerSub: string; size?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total === 0) return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="38" fill="none" stroke="#e5e7eb" strokeWidth="14" />
      <text x="50" y="54" textAnchor="middle" fontSize="14" fill={C.muted}>–</text>
    </svg>
  );
  const r = 38, circ = 2 * Math.PI * r;
  let off = -0.25 * circ;
  const segs = data.filter(d => d.value > 0).map(d => {
    const len = (d.value / total) * circ;
    const el = <circle key={d.label} cx="50" cy="50" r={r} fill="none" stroke={d.color}
      strokeWidth="14" strokeDasharray={`${len} ${circ - len}`} strokeDashoffset={-off} />;
    off += len; return el;
  });
  return (
    <svg width={size} height={size} viewBox="0 0 100 100">
      {segs}
      <text x="50" y="46" textAnchor="middle" fontSize="18" fontWeight="800" fill={C.text}>{centerLabel}</text>
      <text x="50" y="60" textAnchor="middle" fontSize="8" fill={C.textSec}>{centerSub}</text>
    </svg>
  );
}

// ── Pool Toggle ──────────────────────────────────────────────────────
function Toggle({ value, onChange }: { value: "open" | "closed"; onChange: (v: "open" | "closed") => void }) {
  const btn = (v: "open" | "closed", label: string): React.CSSProperties => ({
    padding: "5px 14px", fontSize: 12, fontWeight: v === value ? 700 : 500,
    border: "none", borderRadius: 6, cursor: "pointer",
    background: v === value ? C.text : "transparent",
    color: v === value ? C.white : C.textSec, transition: "all 0.15s",
  });
  return (
    <div style={{ display: "inline-flex", gap: 2, background: "#f1f5f9", borderRadius: 8, padding: 2 }}>
      <button style={btn("open", "Offene Fälle")} onClick={() => onChange("open")}>Offene Fälle</button>
      <button style={btn("closed", "Geschlossene Fälle")} onClick={() => onChange("closed")}>Geschlossene Fälle</button>
    </div>
  );
}

// ── QuotaBar ─────────────────────────────────────────────────────────
function QuotaBar({ label, filled, total, pct }: {
  label: string; filled: number; total: number; pct: number | null;
}) {
  if (pct === null) return (
    <div style={{ marginBottom: 12, opacity: 0.35 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{label}</span>
        <span style={{ fontSize: 12, color: C.muted }}>n/a</span>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: "#e5e7eb" }} />
    </div>
  );
  const col = pct >= 90 ? C.complete : pct >= 70 ? C.warn : C.incomplete;
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 3 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 700, color: col }}>
          {pct.toFixed(0)}%
          <span style={{ fontWeight: 400, color: C.textSec, fontSize: 11, marginLeft: 4 }}>{filled}/{total}</span>
        </span>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: "#e5e7eb", overflow: "hidden" }}>
        <div style={{ height: "100%", borderRadius: 5, width: `${Math.max(pct, 1.5)}%`, background: col, transition: "width 0.4s" }} />
      </div>
    </div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────
function Kpi({ label, value, sub, color, icon }: {
  label: string; value: number | string; sub?: string; color: string; icon: string;
}) {
  return (
    <div style={{ background: C.white, borderRadius: 10, padding: "14px 18px", border: `1px solid ${C.border}`, flex: "1 1 0", minWidth: 120 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 18 }}>{icon}</span>
        <span style={{ fontSize: 11, color: C.textSec, fontWeight: 500 }}>{label}</span>
      </div>
      <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: C.textSec, marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

// ── Top Rules ────────────────────────────────────────────────────────
function TopRules({ rules }: { rules: RuleHit[] }) {
  if (!rules.length) return <div style={{ fontSize: 12, color: C.muted, padding: 8 }}>Keine aktiven Meldungen</div>;
  return (
    <div style={{ fontSize: 12 }}>
      {rules.slice(0, 8).map((r, i) => (
        <div key={r.rule_id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 0",
          borderBottom: i < Math.min(rules.length, 8) - 1 ? `1px solid ${C.border}` : "none" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
            background: r.severity === "CRITICAL" ? C.incomplete : C.warn }} />
          <span style={{ flex: 1, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.message}</span>
          <span style={{ fontWeight: 700, fontSize: 13, minWidth: 28, textAlign: "right",
            color: r.severity === "CRITICAL" ? C.incomplete : C.warn }}>{r.count}</span>
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
export default function AnalyticsPanel({ stations, scopeLabel }: Props) {
  const [pool, setPool] = useState<"open" | "closed">("open");

  const agg = useMemo(() => {
    const totalCases = stations.reduce((s, st) => s + st.total_cases, 0);
    const openCases = stations.reduce((s, st) => s + st.open_cases, 0);
    const closedCases = stations.reduce((s, st) => s + st.closed_cases, 0);
    const compDist = { complete: 0, incomplete: 0 };
    const docReports = { done: 0, within_time: 0, overdue: 0, overdue_by_person: [] as { person: string; count: number }[] };
    const ackMonth = { ack_count: 0, shift_count: 0 };
    const qMap: Record<string, { label: string; ao: boolean; ac: boolean; of: number; ot: number; cf: number; ct: number }> = {};
    const ruleMap: Record<string, RuleHit> = {};

    for (const st of stations) {
      compDist.complete += st.completeness_dist.complete;
      compDist.incomplete += st.completeness_dist.incomplete;
      docReports.done += st.doc_reports.done;
      docReports.within_time += st.doc_reports.within_time;
      docReports.overdue += st.doc_reports.overdue;
      ackMonth.ack_count += st.ack_this_month.ack_count;
      ackMonth.shift_count += st.ack_this_month.shift_count;
      for (const q of st.completeness_quotas) {
        if (!qMap[q.key]) qMap[q.key] = { label: q.label, ao: q.applies_open, ac: q.applies_closed, of: 0, ot: 0, cf: 0, ct: 0 };
        qMap[q.key].of += q.open_filled; qMap[q.key].ot += q.open_total;
        qMap[q.key].cf += q.closed_filled; qMap[q.key].ct += q.closed_total;
      }
      for (const r of st.top_rules) {
        if (!ruleMap[r.rule_id]) ruleMap[r.rule_id] = { ...r, count: 0 };
        ruleMap[r.rule_id].count += r.count;
      }
    }

    // Aggregate overdue_by_person across stations
    const personMap: Record<string, number> = {};
    for (const st of stations) {
      for (const p of st.doc_reports.overdue_by_person) {
        personMap[p.person] = (personMap[p.person] || 0) + p.count;
      }
    }
    docReports.overdue_by_person = Object.entries(personMap)
      .sort((a, b) => b[1] - a[1])
      .map(([person, count]) => ({ person, count }));

    const quotas: CompletenessQuota[] = Object.entries(qMap).map(([key, v]) => ({
      key, label: v.label, applies_open: v.ao, applies_closed: v.ac,
      open_filled: v.of, open_total: v.ot, open_pct: v.ot > 0 ? Math.round(v.of / v.ot * 1000) / 10 : null,
      closed_filled: v.cf, closed_total: v.ct, closed_pct: v.ct > 0 ? Math.round(v.cf / v.ct * 1000) / 10 : null,
    }));
    const topRules = Object.values(ruleMap).sort((a, b) => b.count - a.count).slice(0, 10);
    return { totalCases, openCases, closedCases, compDist, docReports, ackMonth, quotas, topRules };
  }, [stations]);

  const visQ = agg.quotas.filter(q => pool === "open" ? q.applies_open : q.applies_closed);
  const qP = (q: CompletenessQuota) => pool === "open" ? q.open_pct : q.closed_pct;
  const qF = (q: CompletenessQuota) => pool === "open" ? q.open_filled : q.closed_filled;
  const qT = (q: CompletenessQuota) => pool === "open" ? q.open_total : q.closed_total;

  const withData = visQ.filter(q => qP(q) !== null);
  const avgPct = withData.length > 0 ? Math.round(withData.reduce((s, q) => s + (qP(q) ?? 0), 0) / withData.length) : 100;
  const avgCol = avgPct >= 90 ? C.complete : avgPct >= 70 ? C.warn : C.incomplete;
  const completePct = agg.totalCases > 0 ? Math.round(agg.compDist.complete / agg.totalCases * 100) : 100;

  const card: React.CSSProperties = {
    background: C.white, borderRadius: 12, padding: 20,
    border: `1px solid ${C.border}`, boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  };

  return (
    <div style={{ marginTop: 8, marginBottom: 8 }}>
      {/* Titel */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, paddingBottom: 12, borderBottom: `2px solid ${C.border}` }}>
        <span style={{ fontSize: 18 }}>📊</span>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>Auswertung</span>
        <span style={{ fontSize: 12, color: C.textSec }}>— {scopeLabel}</span>
      </div>

      {/* KPI-Reihe 1: Fälle + Vollständigkeit + ACK */}
      <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
        <Kpi icon="📁" label="Fälle gesamt" value={agg.totalCases}
          sub={`${agg.openCases} offen · ${agg.closedCases} geschlossen`} color={C.text} />
        <Kpi icon="🎯" label="Ø Vollständigkeit" value={`${avgPct}%`}
          sub={`${pool === "open" ? "offene" : "geschlossene"} Fälle`} color={avgCol} />
        <Kpi icon="✅" label="Quittiert" value={agg.ackMonth.ack_count} sub="diesen Monat" color={C.ack} />
        <Kpi icon="⏭" label="Erinnert" value={agg.ackMonth.shift_count} sub="diesen Monat" color={C.shift} />
      </div>

      {/* KPI-Reihe 2: Austrittsberichte */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <Kpi icon="📝" label="Berichte erledigt" value={agg.docReports.done}
          sub={`von ${agg.closedCases} geschlossenen Fällen`} color={C.complete} />
        <Kpi icon="⏳" label="Im Zeitfenster" value={agg.docReports.within_time}
          sub="< 10 Tage nach Austritt" color={C.warn} />
        <Kpi icon="🚨" label="Überfällig" value={agg.docReports.overdue}
          sub="≥ 10 Tage nach Austritt" color={C.incomplete} />
      </div>

      {/* Haupt-Grid: Donut + Quoten */}
      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 14, marginBottom: 14 }}>
        {/* Donut */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>Vollständigkeit</div>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
            <Donut data={[
              { label: "Vollständig", value: agg.compDist.complete, color: C.complete },
              { label: "Unvollständig", value: agg.compDist.incomplete, color: C.incomplete },
            ]} centerLabel={`${completePct}%`} centerSub="vollständig" />
          </div>
          {[
            { l: "Vollständig", v: agg.compDist.complete, c: C.complete, bg: C.completeBg },
            { l: "Unvollständig", v: agg.compDist.incomplete, c: C.incomplete, bg: C.incompleteBg },
          ].map(d => (
            <div key={d.l} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
              background: d.bg, borderRadius: 6, padding: "5px 10px", marginBottom: 4, fontSize: 12 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: d.c }} />
                <span style={{ color: C.text }}>{d.l}</span>
              </span>
              <span style={{ fontWeight: 700, color: d.c }}>{d.v}
                <span style={{ fontWeight: 400, color: C.textSec, marginLeft: 3 }}>
                  ({agg.totalCases > 0 ? Math.round(d.v / agg.totalCases * 100) : 0}%)
                </span>
              </span>
            </div>
          ))}
        </div>

        {/* Erfüllungsquoten */}
        <div style={card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
              Erfüllungsquoten
              <span style={{ fontWeight: 400, color: C.textSec, marginLeft: 6, fontSize: 11 }}>
                ({pool === "open" ? agg.openCases : agg.closedCases} Fälle)
              </span>
            </div>
            <Toggle value={pool} onChange={setPool} />
          </div>
          {visQ.length === 0 ? (
            <div style={{ fontSize: 12, color: C.muted, padding: 12 }}>Keine Metriken für {pool === "open" ? "offene" : "geschlossene"} Fälle</div>
          ) : visQ.map(q => <QuotaBar key={q.key} label={q.label} filled={qF(q)} total={qT(q)} pct={qP(q)} />)}
        </div>
      </div>

      {/* Untere Reihe: Überfällige Berichte + Top Meldungen */}
      <div style={{ display: "grid", gridTemplateColumns: agg.docReports.overdue_by_person.length > 0 ? "1fr 1fr" : "1fr", gap: 14 }}>
        {agg.docReports.overdue_by_person.length > 0 && (
          <div style={card}>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
              Überfällige Berichte nach Person
              <span style={{ fontWeight: 400, color: C.textSec, fontSize: 11, marginLeft: 6 }}>≥ 10 Tage</span>
            </div>
            <div style={{ fontSize: 12 }}>
              {agg.docReports.overdue_by_person.slice(0, 8).map((p, i) => (
                <div key={p.person} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "7px 0", borderBottom: i < Math.min(agg.docReports.overdue_by_person.length, 8) - 1 ? `1px solid ${C.border}` : "none" }}>
                  <span style={{ color: C.text }}>{p.person}</span>
                  <span style={{ fontWeight: 700, color: C.incomplete, fontSize: 14 }}>{p.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>Häufigste offene Meldungen</div>
          <TopRules rules={agg.topRules} />
        </div>
      </div>
    </div>
  );
}
