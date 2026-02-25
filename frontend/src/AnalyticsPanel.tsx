/**
 * AnalyticsPanel — BI-Auswertung für Direktion / Übersicht
 *
 * Struktur:
 *   KPI-Reihe: Fälle | Langlieger | Dok nachgefasst | Dok begründet geschoben
 *   Grid: Donut (Dokumentation) | Erfüllungsquoten
 *   Abschnitt: Austrittsdokumentation (Berichte + Überfällige Personen)
 *   Tabelle: Häufigste Meldungen
 */
import { useMemo, useState } from "react";

// ── Types ────────────────────────────────────────────────────────────
export type CompletenessQuota = {
  key: string; label: string; category: "ongoing" | "exit";
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
  severity_dist: { critical: number; warn: number; ok: number };
  langlieger_count: number;
  doc_reports: DocReports;
  ack_this_month: { ack_count: number; shift_count: number };
  completeness_quotas: CompletenessQuota[];
  top_rules: RuleHit[];
};
type Props = { stations: StationAnalytics[]; scopeLabel: string };

// ── Farben ───────────────────────────────────────────────────────────
const C = {
  ok: "#22c55e", okBg: "#f0fdf4",
  warn: "#f59e0b", warnBg: "#fffbeb",
  crit: "#ef4444", critBg: "#fef2f2",
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
      <text x="50" y="50" textAnchor="middle" dominantBaseline="central" fontSize="13" fill={C.muted}>Keine Daten</text>
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
  const btn = (v: "open" | "closed"): React.CSSProperties => ({
    padding: "5px 14px", fontSize: 12, fontWeight: v === value ? 700 : 500,
    border: "none", borderRadius: 6, cursor: "pointer",
    background: v === value ? C.text : "transparent",
    color: v === value ? C.white : C.textSec, transition: "all 0.15s",
  });
  return (
    <div style={{ display: "inline-flex", gap: 2, background: "#f1f5f9", borderRadius: 8, padding: 2 }}>
      <button style={btn("open")} onClick={() => onChange("open")}>Offene Fälle</button>
      <button style={btn("closed")} onClick={() => onChange("closed")}>Geschlossene Fälle</button>
    </div>
  );
}

// ── QuotaBar ─────────────────────────────────────────────────────────
function QuotaBar({ label, filled, total, pct, category = "ongoing", pool = "open" }: {
  label: string; filled: number; total: number; pct: number | null;
  category?: "ongoing" | "exit"; pool?: "open" | "closed";
}) {
  // Austritts-Quotas bei offenen Fällen → "fällig bei Austritt"
  if (category === "exit" && pool === "open") return (
    <div style={{ marginBottom: 12, opacity: 0.35 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{label}</span>
        <span style={{ fontSize: 11, color: "#6366f1", fontStyle: "italic" }}>fällig bei Austritt</span>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: "#eef2ff" }} />
    </div>
  );
  // Keine Fälle im Pool → 0/0
  if (pct === null || total === 0) return (
    <div style={{ marginBottom: 12, opacity: 0.45 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{label}</span>
        <span style={{ fontSize: 12, color: C.muted }}>– <span style={{ fontSize: 11 }}>keine Fälle</span></span>
      </div>
      <div style={{ height: 10, borderRadius: 5, background: "#e5e7eb" }} />
    </div>
  );
  const col = pct >= 90 ? C.ok : pct >= 70 ? C.warn : C.crit;
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
            background: r.severity === "CRITICAL" ? C.crit : C.warn }} />
          <span style={{ flex: 1, color: C.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.message}</span>
          <span style={{ fontWeight: 700, fontSize: 13, minWidth: 28, textAlign: "right",
            color: r.severity === "CRITICAL" ? C.crit : C.warn }}>{r.count}</span>
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
    const sevDist = { critical: 0, warn: 0, ok: 0 };
    const docReports = { done: 0, within_time: 0, overdue: 0, overdue_by_person: [] as { person: string; count: number }[] };
    const ackMonth = { ack_count: 0, shift_count: 0 };
    let langlieger = 0;
    const qMap: Record<string, { label: string; cat: "ongoing" | "exit"; of: number; ot: number; cf: number; ct: number }> = {};
    const ruleMap: Record<string, RuleHit> = {};

    for (const st of stations) {
      sevDist.critical += st.severity_dist?.critical ?? 0;
      sevDist.warn += st.severity_dist?.warn ?? 0;
      sevDist.ok += st.severity_dist?.ok ?? 0;
      langlieger += st.langlieger_count ?? 0;
      docReports.done += st.doc_reports.done;
      docReports.within_time += st.doc_reports.within_time;
      docReports.overdue += st.doc_reports.overdue;
      ackMonth.ack_count += st.ack_this_month.ack_count;
      ackMonth.shift_count += st.ack_this_month.shift_count;
      for (const q of st.completeness_quotas) {
        if (!qMap[q.key]) qMap[q.key] = { label: q.label, cat: q.category ?? "ongoing", of: 0, ot: 0, cf: 0, ct: 0 };
        qMap[q.key].of += q.open_filled; qMap[q.key].ot += q.open_total;
        qMap[q.key].cf += q.closed_filled; qMap[q.key].ct += q.closed_total;
      }
      for (const r of st.top_rules) {
        if (!ruleMap[r.rule_id]) ruleMap[r.rule_id] = { ...r, count: 0 };
        ruleMap[r.rule_id].count += r.count;
      }
    }

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
      key, label: v.label, category: v.cat,
      open_filled: v.of, open_total: v.ot, open_pct: v.ot > 0 ? Math.round(v.of / v.ot * 1000) / 10 : null,
      closed_filled: v.cf, closed_total: v.ct, closed_pct: v.ct > 0 ? Math.round(v.cf / v.ct * 1000) / 10 : null,
    }));
    const topRules = Object.values(ruleMap).sort((a, b) => b.count - a.count).slice(0, 10);
    return { totalCases, openCases, closedCases, sevDist, langlieger, docReports, ackMonth, quotas, topRules };
  }, [stations]);

  // Feste Quota-Reihenfolge: immer alle anzeigen, stabile Positionen
  const FIXED_QUOTA_ORDER: { key: string; label: string; category: "ongoing" | "exit" }[] = [
    { key: "honos",           label: "HoNOS",              category: "ongoing" },
    { key: "bscl",            label: "BSCL",               category: "ongoing" },
    { key: "bfs",             label: "BFS Verlauf",         category: "ongoing" },
    { key: "treatment_plan",  label: "Behandlungsplan",     category: "ongoing" },
    { key: "spiges_stamm",    label: "SpiGes Stammdaten",   category: "ongoing" },
    { key: "psychopharmaka",  label: "Psychopharmaka",      category: "ongoing" },
    { key: "fu",              label: "FU-Anordnung",        category: "ongoing" },
    { key: "spiges_austritt", label: "SpiGes Austritt",     category: "exit" },
    { key: "doc_austritt",    label: "Dok Austritt",        category: "exit" },
  ];

  const allQ = FIXED_QUOTA_ORDER.map(def => {
    const q = agg.quotas.find(x => x.key === def.key);
    const filled = q ? (pool === "open" ? q.open_filled : q.closed_filled) : 0;
    const total = q ? (pool === "open" ? q.open_total : q.closed_total) : 0;
    const pct = total > 0 ? Math.round(filled / total * 1000) / 10 : null;
    return { key: def.key, label: def.label, category: def.category, filled, total, pct };
  });

  const totalSev = agg.sevDist.critical + agg.sevDist.warn + agg.sevDist.ok;
  const okPct = totalSev > 0 ? Math.round(agg.sevDist.ok / totalSev * 100) : 100;

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

      {/* KPI-Reihe */}
      <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
        <Kpi icon="📁" label="Fälle gesamt" value={agg.totalCases}
          sub={`${agg.openCases} offen · ${agg.closedCases} geschlossen`} color={C.text} />
        <Kpi icon="🏥" label="Langlieger" value={agg.langlieger}
          sub="≥ 50 Tage, Fall offen" color={agg.langlieger > 0 ? C.warn : C.ok} />
        <Kpi icon="📝" label="Dok nachgefasst" value={agg.ackMonth.ack_count} sub="diesen Monat" color={C.ack} />
        <Kpi icon="⏭" label="Dok begründet geschoben" value={agg.ackMonth.shift_count} sub="diesen Monat" color={C.shift} />
      </div>

      {/* Grid: Donut + Quoten */}
      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 14, marginBottom: 14 }}>
        {/* Donut — Dokumentation */}
        <div style={card}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>Dokumentation vollständig</div>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
            <Donut data={[
              { label: "Kritisch", value: agg.sevDist.critical, color: C.crit },
              { label: "Warnung", value: agg.sevDist.warn, color: C.warn },
              { label: "OK", value: agg.sevDist.ok, color: C.ok },
            ]} centerLabel={`${okPct}%`} centerSub="vollständig" />
          </div>
          {[
            { l: "Vollständig", v: agg.sevDist.ok, c: C.ok, bg: C.okBg },
            { l: "Warnung", v: agg.sevDist.warn, c: C.warn, bg: C.warnBg },
            { l: "Kritisch", v: agg.sevDist.critical, c: C.crit, bg: C.critBg },
          ].map(d => (
            <div key={d.l} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
              background: d.bg, borderRadius: 6, padding: "5px 10px", marginBottom: 4, fontSize: 12 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: d.c }} />
                <span style={{ color: C.text }}>{d.l}</span>
              </span>
              <span style={{ fontWeight: 700, color: d.c }}>{d.v}
                <span style={{ fontWeight: 400, color: C.textSec, marginLeft: 3 }}>
                  ({totalSev > 0 ? Math.round(d.v / totalSev * 100) : 0}%)
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
          {allQ.length === 0 ? (
            <div style={{ fontSize: 12, color: C.muted, padding: 12 }}>Keine Metriken verfügbar</div>
          ) : allQ.map(q => <QuotaBar key={q.key} label={q.label} filled={q.filled} total={q.total} pct={q.pct} category={q.category} pool={pool} />)}
        </div>
      </div>

      {/* ── Abschnitt: Austrittsdokumentation ────────────────────────── */}
      <div style={{ ...card, marginBottom: 14 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 14, paddingBottom: 8, borderBottom: `1px solid ${C.border}` }}>
          Austrittsdokumentation
          <span style={{ fontWeight: 400, color: C.textSec, fontSize: 11, marginLeft: 8 }}>{agg.closedCases} geschlossene Fälle</span>
        </div>

        {/* KPIs inline */}
        <div style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
          <Kpi icon="✅" label="Berichte erledigt" value={agg.docReports.done}
            sub={`von ${agg.closedCases} geschlossenen`} color={C.ok} />
          <Kpi icon="⏳" label="Im Zeitfenster" value={agg.docReports.within_time}
            sub="< 10 Tage nach Austritt" color={C.warn} />
          <Kpi icon="🚨" label="Überfällig" value={agg.docReports.overdue}
            sub="≥ 10 Tage nach Austritt" color={C.crit} />
        </div>

        {/* Überfällige nach Person (wenn vorhanden) */}
        {agg.docReports.overdue_by_person.length > 0 && (
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>
              Überfällige Berichte nach fallführender Person
            </div>
            <div style={{ fontSize: 12 }}>
              {agg.docReports.overdue_by_person.slice(0, 8).map((p, i) => (
                <div key={p.person} style={{ display: "flex", alignItems: "center", justifyContent: "space-between",
                  padding: "6px 0", borderBottom: i < Math.min(agg.docReports.overdue_by_person.length, 8) - 1 ? `1px solid ${C.border}` : "none" }}>
                  <span style={{ color: C.text }}>{p.person}</span>
                  <span style={{ fontWeight: 700, color: C.crit, fontSize: 14 }}>{p.count}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Häufigste Meldungen */}
      <div style={card}>
        <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>Häufigste offene Meldungen</div>
        <TopRules rules={agg.topRules} />
      </div>
    </div>
  );
}
