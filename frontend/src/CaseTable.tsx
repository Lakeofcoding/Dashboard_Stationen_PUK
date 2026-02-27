/**
 * CaseTable v7 – Aufgabenorientierte Arbeitsliste.
 *
 * Features:
 * - ACK-Fortschritt pro Fall (X/Y erledigt)
 * - Filter: Alle / Offen / Kritisch / Erledigt
 * - Dringlichkeits-Sortierung (Severity × offene Alerts × Tage)
 * - Expandierbare Zeilen mit Inline-Alert-Liste
 * - Letzte Aktion (wer hat wann quittiert)
 * - Globaler Fortschrittsbalken im Header
 */
import { useState, useMemo, useCallback } from "react";
import type { CaseSummary, ParameterStatus, Severity } from "./types";

/* ───── Sortierung ───── */
type SortKey = "urgency" | "case_id" | "station_id" | "severity" | "progress" | "days";
type SortDir = "asc" | "desc";
type FilterMode = "all" | "open" | "critical" | "done";

const SEV_ORDER: Record<Severity, number> = { CRITICAL: 0, WARN: 1, OK: 2 };

/** Dringlichkeits-Score: niedrig = dringender */
function urgencyScore(c: CaseSummary): number {
  const sevWeight = SEV_ORDER[c.severity] * 1000;
  const openWeight = -(c.open_alerts ?? 0) * 100;
  const daysWeight = -(c.days_since_admission ?? 0);
  return sevWeight + openWeight + daysWeight;
}

function cmpVal(a: CaseSummary, b: CaseSummary, key: SortKey): number {
  switch (key) {
    case "urgency": return urgencyScore(a) - urgencyScore(b);
    case "case_id": return a.case_id.localeCompare(b.case_id);
    case "station_id": return a.station_id.localeCompare(b.station_id);
    case "severity": return SEV_ORDER[a.severity] - SEV_ORDER[b.severity];
    case "progress": {
      const pa = (a.total_alerts ?? 0) > 0 ? (a.acked_alerts ?? 0) / (a.total_alerts ?? 1) : 1;
      const pb = (b.total_alerts ?? 0) > 0 ? (b.acked_alerts ?? 0) / (b.total_alerts ?? 1) : 1;
      return pa - pb;
    }
    case "days": return (b.days_since_admission ?? 0) - (a.days_since_admission ?? 0);
    default: return 0;
  }
}

function daysSince(isoDate: string): number {
  return Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000);
}

function timeAgo(isoDate: string): string {
  const mins = Math.floor((Date.now() - new Date(isoDate).getTime()) / 60000);
  if (mins < 1) return "gerade eben";
  if (mins < 60) return `vor ${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `vor ${hrs}h`;
  return `vor ${Math.floor(hrs / 24)}d`;
}

/* ───── Farben ───── */
const SEV_BADGE: Record<Severity, { bg: string; color: string; border: string }> = {
  CRITICAL: { bg: "#fef2f2", color: "#dc2626", border: "#fca5a5" },
  WARN:     { bg: "#fffbeb", color: "#d97706", border: "#fcd34d" },
  OK:       { bg: "#f0fdf4", color: "#16a34a", border: "#bbf7d0" },
};

const STATUS_DOT: Record<string, string> = {
  ok: "#22c55e", warn: "#f59e0b", critical: "#ef4444", na: "#d1d5db",
};

/* ───── Komponente ───── */
interface Props {
  cases: CaseSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  parameterFilter?: "all" | "completeness" | "medical";
}

export default function CaseTable({ cases, selectedCaseId, onSelectCase, parameterFilter = "all" }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("urgency");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  const toggleSort = useCallback((key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }, [sortKey]);

  /* Filter */
  const filtered = useMemo(() => {
    switch (filterMode) {
      case "open": return cases.filter(c => (c.open_alerts ?? 0) > 0);
      case "critical": return cases.filter(c => c.severity === "CRITICAL");
      case "done": return cases.filter(c => (c.total_alerts ?? 0) > 0 && (c.open_alerts ?? 0) === 0);
      default: return cases;
    }
  }, [cases, filterMode]);

  /* Sort */
  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => { const c = cmpVal(a, b, sortKey); return sortDir === "asc" ? c : -c; });
    return arr;
  }, [filtered, sortKey, sortDir]);

  /* Globaler Fortschritt */
  const globalTotal = useMemo(() => cases.reduce((s, c) => s + (c.total_alerts ?? 0), 0), [cases]);
  const globalAcked = useMemo(() => cases.reduce((s, c) => s + (c.acked_alerts ?? 0), 0), [cases]);
  const globalPct = globalTotal > 0 ? Math.round((globalAcked / globalTotal) * 100) : 100;

  /* Filter-Counts */
  const openCount = useMemo(() => cases.filter(c => (c.open_alerts ?? 0) > 0).length, [cases]);
  const critCount = useMemo(() => cases.filter(c => c.severity === "CRITICAL").length, [cases]);
  const doneCount = useMemo(() => cases.filter(c => (c.total_alerts ?? 0) > 0 && (c.open_alerts ?? 0) === 0).length, [cases]);

  const COLUMNS: { key: SortKey; label: string; width: string; align?: string }[] = [
    { key: "case_id", label: "Fall-Nr.", width: "100px" },
    { key: "station_id", label: "Station", width: "65px" },
    { key: "days", label: "Tage", width: "50px", align: "right" },
    { key: "severity", label: "Status", width: "105px" },
    { key: "progress", label: "Fortschritt", width: "130px" },
  ];

  return (
    <div style={{ width: "100%" }}>
      {/* ── Globaler Fortschrittsbalken ── */}
      <div style={{ marginBottom: 12, padding: "10px 14px", background: "#f8fafc", borderRadius: 8, border: "1px solid #e5e7eb" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: "#374151" }}>
            {cases.length} Fälle · {globalAcked}/{globalTotal} Meldungen bearbeitet
          </span>
          <span style={{ fontSize: 12, fontWeight: 700, color: globalPct === 100 ? "#16a34a" : "#d97706" }}>
            {globalPct}%
          </span>
        </div>
        <div style={{ height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden" }}>
          <div style={{
            height: "100%", borderRadius: 3, transition: "width 0.3s",
            width: `${globalPct}%`,
            background: globalPct === 100 ? "#22c55e" : globalPct >= 50 ? "#3b82f6" : "#f59e0b",
          }} />
        </div>
      </div>

      {/* ── Filter-Buttons ── */}
      <div style={{ display: "flex", gap: 4, marginBottom: 10, flexWrap: "wrap" }}>
        {([
          ["all", `Alle (${cases.length})`],
          ["open", `Offen (${openCount})`],
          ["critical", `Kritisch (${critCount})`],
          ["done", `Erledigt (${doneCount})`],
        ] as [FilterMode, string][]).map(([val, label]) => (
          <button key={val} onClick={() => setFilterMode(val)}
            style={{
              padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 600,
              border: "1px solid", cursor: "pointer", transition: "all 0.15s",
              borderColor: filterMode === val ? (val === "critical" ? "#ef4444" : val === "open" ? "#f59e0b" : val === "done" ? "#22c55e" : "#3b82f6") : "#d1d5db",
              background: filterMode === val ? (val === "critical" ? "#fef2f2" : val === "open" ? "#fffbeb" : val === "done" ? "#f0fdf4" : "#eff6ff") : "#fff",
              color: filterMode === val ? (val === "critical" ? "#dc2626" : val === "open" ? "#92400e" : val === "done" ? "#166534" : "#1d4ed8") : "#6b7280",
            }}>
            {label}
          </button>
        ))}
      </div>

      {/* ── Tabelle ── */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #e5e7eb", background: "#f9fafb" }}>
              <th style={{ width: 28, padding: "10px 4px", position: "sticky", top: 0, background: "#f9fafb", zIndex: 2 }} />
              {COLUMNS.map(col => (
                <th key={col.key} onClick={() => toggleSort(col.key)}
                  style={{
                    padding: "10px 8px", textAlign: (col.align as any) || "left",
                    fontWeight: 600, fontSize: 11, color: "#6b7280",
                    textTransform: "uppercase", letterSpacing: 0.5,
                    cursor: "pointer", userSelect: "none", whiteSpace: "nowrap",
                    width: col.width, position: "sticky", top: 0, background: "#f9fafb", zIndex: 2,
                  }}>
                  {col.label} {sortKey === col.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
                </th>
              ))}
              <th style={{
                padding: "10px 8px", textAlign: "left", fontWeight: 600, fontSize: 11,
                color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.5,
                position: "sticky", top: 0, background: "#f9fafb", zIndex: 2,
              }}>Letzte Aktion</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={COLUMNS.length + 2} style={{ padding: 32, color: "#9ca3af", textAlign: "center", fontSize: 14 }}>
                  {filterMode === "all" ? "Keine Fälle für diese Station." :
                   filterMode === "open" ? "🎉 Keine offenen Meldungen – alles bearbeitet!" :
                   filterMode === "critical" ? "✓ Keine kritischen Fälle." :
                   "Noch keine Fälle vollständig bearbeitet."}
                </td>
              </tr>
            ) : sorted.map(c => (
              <CaseRow key={c.case_id} c={c}
                isSelected={selectedCaseId === c.case_id}
                isExpanded={expandedCase === c.case_id}
                onSelect={() => onSelectCase(c.case_id)}
                onToggleExpand={() => setExpandedCase(prev => prev === c.case_id ? null : c.case_id)}
                parameterFilter={parameterFilter} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ───── CaseRow mit Expand ───── */
function CaseRow({ c, isSelected, isExpanded, onSelect, onToggleExpand, parameterFilter }: {
  c: CaseSummary; isSelected: boolean; isExpanded: boolean;
  onSelect: () => void; onToggleExpand: () => void; parameterFilter: string;
}) {
  const days = c.days_since_admission ?? daysSince(c.admission_date);
  const total = c.total_alerts ?? 0;
  const acked = c.acked_alerts ?? 0;
  const open = c.open_alerts ?? 0;
  const pct = total > 0 ? Math.round((acked / total) * 100) : 100;
  const allDone = total > 0 && open === 0;
  const sev = SEV_BADGE[c.severity];

  const params = c.parameter_status ?? [];
  const problems = parameterFilter === "all"
    ? params.filter(p => p.status === "critical" || p.status === "warn")
    : params.filter(p => (p.status === "critical" || p.status === "warn") && p.group === parameterFilter);

  return (
    <>
      <tr onClick={onSelect}
        style={{
          borderBottom: isExpanded ? "none" : "1px solid #f3f4f6", cursor: "pointer",
          background: isSelected ? "#dbeafe" : allDone ? "#fafff9" : undefined,
          transition: "background 0.1s", opacity: allDone && !isSelected ? 0.7 : 1,
          borderLeft: isSelected ? "3px solid #2563eb" : "3px solid transparent",
        }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "#f9fafb"; }}
        onMouseLeave={e => { e.currentTarget.style.background = isSelected ? "#dbeafe" : allDone ? "#fafff9" : ""; }}>
        {/* Expand Toggle */}
        <td style={{ padding: "8px 4px", textAlign: "center" }}>
          {problems.length > 0 && (
            <button onClick={e => { e.stopPropagation(); onToggleExpand(); }}
              style={{
                width: 22, height: 22, borderRadius: 4, border: "1px solid #d1d5db",
                background: isExpanded ? "#eff6ff" : "#fff", cursor: "pointer",
                fontSize: 10, fontWeight: 700, color: "#6b7280", display: "inline-flex",
                alignItems: "center", justifyContent: "center", transition: "all 0.15s",
              }}>
              {isExpanded ? "▾" : "▸"}
            </button>
          )}
        </td>
        <td style={{ padding: "8px 8px", fontWeight: 700, fontFamily: "monospace", fontSize: 13 }}>{c.case_id}</td>
        <td style={{ padding: "8px 8px", fontWeight: 600, fontSize: 12 }}>{c.station_id}</td>
        <td style={{ padding: "8px 8px", textAlign: "right", fontFamily: "monospace", fontSize: 12 }}>{days}d</td>
        <td style={{ padding: "8px 8px" }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700,
            background: sev.bg, color: sev.color, border: `1px solid ${sev.border}`,
          }}>
            {c.severity === "CRITICAL" ? "‼" : c.severity === "WARN" ? "⚠" : "✓"}
            {" "}{open > 0 ? `${open} offen` : "OK"}
          </span>
        </td>
        <td style={{ padding: "8px 8px" }}>
          {total > 0 ? (
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ flex: 1, height: 6, background: "#e5e7eb", borderRadius: 3, overflow: "hidden", minWidth: 50 }}>
                <div style={{
                  height: "100%", borderRadius: 3, transition: "width 0.3s",
                  width: `${pct}%`,
                  background: allDone ? "#22c55e" : pct >= 50 ? "#3b82f6" : "#f59e0b",
                }} />
              </div>
              <span style={{ fontSize: 11, fontWeight: 600, color: allDone ? "#16a34a" : "#6b7280", whiteSpace: "nowrap" }}>
                {acked}/{total}
              </span>
            </div>
          ) : (
            <span style={{ fontSize: 11, color: "#9ca3af" }}>—</span>
          )}
        </td>
        <td style={{ padding: "8px 8px", fontSize: 11, color: "#6b7280" }}>
          {c.last_ack_by ? (
            <span title={c.last_ack_at ?? ""}>
              <span style={{ fontWeight: 600, color: "#374151" }}>{c.last_ack_by}</span>
              {" "}{c.last_ack_at ? timeAgo(c.last_ack_at) : ""}
            </span>
          ) : (
            <span style={{ color: "#d1d5db" }}>—</span>
          )}
        </td>
      </tr>
      {/* ── Expandierte Alert-Liste ── */}
      {isExpanded && problems.length > 0 && (
        <tr>
          <td colSpan={7} style={{ padding: 0, borderBottom: "1px solid #e5e7eb" }}>
            <div style={{ padding: "8px 12px 10px 42px", background: "#f8fafc", borderTop: "1px dashed #e5e7eb" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {problems.map(p => <ParamPill key={p.id} p={p} />)}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ───── Parameter-Pill ───── */
function ParamPill({ p }: { p: ParameterStatus }) {
  const [hovered, setHovered] = useState(false);
  const dotColor = STATUS_DOT[p.status] ?? "#d1d5db";
  return (
    <div style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 3,
        padding: "3px 8px", borderRadius: 4, fontSize: 11, fontWeight: 600,
        background: `${dotColor}14`, color: dotColor, border: `1px solid ${dotColor}44`,
        whiteSpace: "nowrap", cursor: "default",
      }}>
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor, flexShrink: 0 }} />
        {p.label}
      </div>
      {hovered && p.detail && (
        <div style={{
          position: "absolute", bottom: "calc(100% + 4px)", left: "50%",
          transform: "translateX(-50%)", padding: "4px 8px",
          background: "#1f2937", color: "#fff", fontSize: 11,
          borderRadius: 4, whiteSpace: "nowrap", zIndex: 50, pointerEvents: "none",
        }}>{p.detail}</div>
      )}
    </div>
  );
}
