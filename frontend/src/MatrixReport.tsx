/**
 * MatrixReport – Heatmap-Matrix für Tages-/Wochenberichte.
 *
 * Zeilen = Fälle, Spalten = Parameter (gruppiert).
 * Jede Zelle = farbiger Punkt (grün/gelb/rot/grau).
 * Summary-Zeile unten mit Zählern.
 * CSV-Export pro Spaltengruppe.
 */
import React, { useState, useMemo } from "react";
import type { CaseSummary, ParameterStatus } from "./types";

/* ───── Spalten-Gruppen ───── */
interface ColDef {
  id: string;
  label: string;
  short: string;
}

const GROUPS: { key: string; category: "completeness" | "medical"; label: string; icon: string; cols: ColDef[] }[] = [
  {
    key: "scores",
    category: "completeness",
    label: "Scores",
    icon: "📊",
    cols: [
      { id: "honos_entry", label: "HoNOS Eintritt", short: "HoN ET" },
      { id: "honos_discharge", label: "HoNOS Austritt", short: "HoN AT" },
      { id: "honos_delta", label: "HoNOS Δ", short: "HoN Δ" },
      { id: "bscl_entry", label: "BSCL Eintritt", short: "BSC ET" },
      { id: "bscl_discharge", label: "BSCL Austritt", short: "BSC AT" },
      { id: "bscl_delta", label: "BSCL Δ", short: "BSC Δ" },
    ],
  },
  {
    key: "documentation",
    category: "completeness",
    label: "Dokumentation",
    icon: "📋",
    cols: [
      { id: "bfs", label: "BFS", short: "BFS" },
      { id: "sdep", label: "SDEP", short: "SDEP" },
      { id: "treatment_plan", label: "Behandlungsplan", short: "BehPl" },
      { id: "doc_completion", label: "Dok.Abschluss", short: "Dok.A" },
    ],
  },
  {
    key: "spiges",
    category: "completeness",
    label: "SpiGes / Admin",
    icon: "📑",
    cols: [
      { id: "zivilstand", label: "Zivilstand", short: "Zivil" },
      { id: "aufenthaltsort", label: "Aufenthaltsort", short: "AufO" },
      { id: "beschaeftigung", label: "Beschäftigung", short: "Besch" },
      { id: "schulbildung", label: "Schulbildung", short: "Schul" },
      { id: "einweisende_instanz", label: "Einw. Instanz", short: "EInst" },
      { id: "behandlungsgrund", label: "Beh.grund", short: "BGrd" },
      { id: "eintrittsart", label: "Eintrittsart", short: "EArt" },
      { id: "klasse", label: "Klasse", short: "Kl." },
      { id: "behandlung_typ", label: "Beh.typ", short: "BTyp" },
      { id: "psychopharmaka", label: "Psychopharmaka", short: "Phar" },
    ],
  },
  {
    key: "fu_lang",
    category: "completeness",
    label: "FU / Langlieger",
    icon: "⚖️",
    cols: [
      { id: "fu_bei_eintritt", label: "FU Eintritt", short: "FU ET" },
      { id: "fu_ablauf", label: "FU Ablauf", short: "FU Ab" },
      { id: "langlieger", label: "Langlieger", short: "Lang" },
    ],
  },
  {
    key: "monitoring",
    category: "medical",
    label: "Klinisches Monitoring",
    icon: "🩺",
    cols: [
      { id: "ekg", label: "EKG", short: "EKG" },
      { id: "clozapin", label: "Clozapin", short: "Cloz" },
      { id: "suicidality", label: "Suizidalität", short: "Suiz" },
      { id: "notfall_bem", label: "Notfall-BEM", short: "NfBm" },
      { id: "notfall_med", label: "Notfall-Med", short: "NfMd" },
      { id: "isolation", label: "Isolation", short: "Iso" },
      { id: "allergies", label: "Allergien", short: "Allg" },
    ],
  },
];

const ALL_COL_IDS = GROUPS.flatMap((g) => g.cols.map((c) => c.id));

/* ───── Farben ───── */
const DOT_COLORS: Record<string, string> = {
  ok: "#22c55e",
  warn: "#f59e0b",
  critical: "#ef4444",
  na: "#e5e7eb",
};

const DOT_BG: Record<string, string> = {
  ok: "#f0fdf4",
  warn: "#fffbeb",
  critical: "#fef2f2",
  na: "#f9fafb",
};

/* ───── Helpers ───── */
function getParamStatus(params: ParameterStatus[], id: string): ParameterStatus | null {
  return params.find((p) => p.id === id) ?? null;
}

function statusSymbol(s: string | null): string {
  switch (s) {
    case "ok": return "✓";
    case "warn": return "!";
    case "critical": return "✕";
    default: return "–";
  }
}

/* ───── Komponente ───── */
interface Props {
  cases: CaseSummary[];
  onSelectCase: (caseId: string) => void;
  authHeaders: Record<string, string>;
  categoryFilter?: "all" | "completeness" | "medical";
}

export default function MatrixReport({ cases, onSelectCase, authHeaders, categoryFilter = "all" }: Props) {
  const visibleGroups = useMemo(() => {
    if (categoryFilter === "all") return GROUPS;
    return GROUPS.filter(g => g.category === categoryFilter);
  }, [categoryFilter]);
  const visibleColIds = useMemo(() => visibleGroups.flatMap(g => g.cols.map(c => c.id)), [visibleGroups]);
  const [hoveredCell, setHoveredCell] = useState<{ caseId: string; colId: string } | null>(null);
  const [filterStatus, setFilterStatus] = useState<"all" | "critical" | "warn" | "issues">("all");

  /* Filter: nur Fälle mit Problemen */
  const filteredCases = useMemo(() => {
    if (filterStatus === "all") return cases;
    return cases.filter((c) => {
      const params = c.parameter_status ?? [];
      if (filterStatus === "critical") return params.some((p) => p.status === "critical");
      if (filterStatus === "warn") return params.some((p) => p.status === "warn");
      if (filterStatus === "issues") return params.some((p) => p.status === "critical" || p.status === "warn");
      return true;
    });
  }, [cases, filterStatus]);

  /* Summary-Zähler pro Spalte */
  const colCounts = useMemo(() => {
    const counts: Record<string, { ok: number; warn: number; critical: number }> = {};
    for (const colId of visibleColIds) {
      counts[colId] = { ok: 0, warn: 0, critical: 0 };
    }
    for (const c of cases) {
      const params = c.parameter_status ?? [];
      for (const colId of visibleColIds) {
        const p = getParamStatus(params, colId);
        if (p && p.status in counts[colId]) {
          counts[colId][p.status as "ok" | "warn" | "critical"]++;
        }
      }
    }
    return counts;
  }, [cases, visibleColIds]);

  const totalIssues = useMemo(() => {
    let crit = 0, warn = 0;
    for (const c of visibleColIds) {
      crit += colCounts[c]?.critical ?? 0;
      warn += colCounts[c]?.warn ?? 0;
    }
    return { crit, warn };
  }, [colCounts, visibleColIds]);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h3 style={{ margin: 0, fontSize: "1.1rem" }}>Tagesbericht – Parameter-Matrix</h3>
          {totalIssues.crit > 0 && (
            <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 8px", borderRadius: 999, background: "#fef2f2", color: "#dc2626", border: "1px solid #fca5a5" }}>
              {totalIssues.crit} kritisch
            </span>
          )}
          {totalIssues.warn > 0 && (
            <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 8px", borderRadius: 999, background: "#fffbeb", color: "#d97706", border: "1px solid #fde68a" }}>
              {totalIssues.warn} Warnungen
            </span>
          )}
        </div>

        {/* Filter */}
        <div style={{ display: "flex", gap: 4 }}>
          {([
            ["all", "Alle"],
            ["issues", "Auffällig"],
            ["critical", "Kritisch"],
            ["warn", "Warnungen"],
          ] as [string, string][]).map(([val, label]) => (
            <button
              key={val}
              onClick={() => setFilterStatus(val as any)}
              style={{
                padding: "4px 10px",
                borderRadius: 6,
                fontSize: 11,
                fontWeight: 600,
                border: "1px solid",
                borderColor: filterStatus === val ? "#3b82f6" : "#d1d5db",
                background: filterStatus === val ? "#eff6ff" : "#fff",
                color: filterStatus === val ? "#1d4ed8" : "#6b7280",
                cursor: "pointer",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Legende */}
      <div style={{ display: "flex", gap: 12, marginBottom: 12, fontSize: 11, color: "#6b7280" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS.ok }} /> OK
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS.warn }} /> Warnung
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS.critical }} /> Kritisch
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: DOT_COLORS.na }} /> N/A
        </span>
      </div>

      {/* Matrix-Tabelle */}
      <div style={{ overflowX: "auto", border: "1px solid #e5e7eb", borderRadius: 8 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, minWidth: 800 }}>
          <thead>
            {/* Gruppenheader */}
            <tr style={{ background: "#f9fafb" }}>
              <th style={{ ...thStyle, width: 90, borderRight: "2px solid #e5e7eb" }} rowSpan={2}>Fall-Nr.</th>
              <th style={{ ...thStyle, width: 50, borderRight: "2px solid #e5e7eb" }} rowSpan={2}>St.</th>
              {visibleGroups.map((g) => (
                <th
                  key={g.key}
                  colSpan={g.cols.length}
                  style={{
                    ...thStyle,
                    textAlign: "center",
                    borderRight: "2px solid #e5e7eb",
                    borderBottom: "1px solid #e5e7eb",
                    fontSize: 11,
                  }}
                >
                  {g.icon} {g.label}
                </th>
              ))}
            </tr>
            {/* Spaltenheader */}
            <tr style={{ background: "#f9fafb" }}>
              {visibleGroups.map((g) =>
                g.cols.map((col, i) => (
                  <th
                    key={col.id}
                    style={{
                      ...thStyle,
                      textAlign: "center",
                      fontSize: 10,
                      padding: "6px 3px",
                      fontWeight: 500,
                      borderRight: i === g.cols.length - 1 ? "2px solid #e5e7eb" : "1px solid #f3f4f6",
                      maxWidth: 50,
                    }}
                    title={col.label}
                  >
                    {col.short}
                  </th>
                ))
              )}
            </tr>
          </thead>
          <tbody>
            {filteredCases.length === 0 ? (
              <tr>
                <td colSpan={2 + visibleColIds.length} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>
                  Keine Fälle mit diesem Filter.
                </td>
              </tr>
            ) : (
              filteredCases.map((c) => {
                const params = c.parameter_status ?? [];
                return (
                  <tr
                    key={c.case_id}
                    onClick={() => onSelectCase(c.case_id)}
                    style={{ cursor: "pointer", borderBottom: "1px solid #f3f4f6" }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#f8fafc"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = ""; }}
                  >
                    <td style={{ padding: "8px 8px", fontWeight: 700, fontFamily: "monospace", fontSize: 12, borderRight: "2px solid #e5e7eb" }}>
                      {c.case_id}
                    </td>
                    <td style={{ padding: "8px 6px", fontSize: 11, fontWeight: 600, borderRight: "2px solid #e5e7eb" }}>
                      {c.station_id}
                    </td>
                    {visibleGroups.map((g) =>
                      g.cols.map((col, i) => {
                        const p = getParamStatus(params, col.id);
                        const status = p?.status ?? "na";
                        const isHovered =
                          hoveredCell?.caseId === c.case_id && hoveredCell?.colId === col.id;

                        return (
                          <td
                            key={col.id}
                            onMouseEnter={() => setHoveredCell({ caseId: c.case_id, colId: col.id })}
                            onMouseLeave={() => setHoveredCell(null)}
                            style={{
                              padding: "6px 3px",
                              textAlign: "center",
                              background: DOT_BG[status],
                              borderRight:
                                i === g.cols.length - 1
                                  ? "2px solid #e5e7eb"
                                  : "1px solid #f3f4f6",
                              position: "relative",
                            }}
                          >
                            <span
                              style={{
                                display: "inline-block",
                                width: 14,
                                height: 14,
                                borderRadius: "50%",
                                background: DOT_COLORS[status],
                                lineHeight: "14px",
                                fontSize: 9,
                                fontWeight: 800,
                                color: status === "na" ? "#9ca3af" : "#fff",
                                textAlign: "center",
                              }}
                            >
                              {statusSymbol(status)}
                            </span>
                            {isHovered && p?.detail && (
                              <div
                                style={{
                                  position: "absolute",
                                  bottom: "calc(100% + 2px)",
                                  left: "50%",
                                  transform: "translateX(-50%)",
                                  padding: "4px 8px",
                                  background: "#1f2937",
                                  color: "#fff",
                                  fontSize: 11,
                                  borderRadius: 4,
                                  whiteSpace: "nowrap",
                                  zIndex: 50,
                                  pointerEvents: "none",
                                }}
                              >
                                <strong>{col.label}:</strong> {p.detail}
                              </div>
                            )}
                          </td>
                        );
                      })
                    )}
                  </tr>
                );
              })
            )}

            {/* Summary-Zeile */}
            <tr style={{ background: "#f1f5f9", borderTop: "2px solid #e5e7eb", fontWeight: 700 }}>
              <td colSpan={2} style={{ padding: "8px 8px", fontSize: 11, borderRight: "2px solid #e5e7eb", color: "#6b7280" }}>
                Σ ({filteredCases.length} Fälle)
              </td>
              {visibleGroups.map((g) =>
                g.cols.map((col, i) => {
                  const cnt = colCounts[col.id] ?? { ok: 0, warn: 0, critical: 0 };
                  const issues = cnt.critical + cnt.warn;
                  return (
                    <td
                      key={col.id}
                      style={{
                        padding: "6px 3px",
                        textAlign: "center",
                        fontSize: 10,
                        borderRight:
                          i === g.cols.length - 1
                            ? "2px solid #e5e7eb"
                            : "1px solid #f3f4f6",
                        color: issues > 0 ? "#dc2626" : "#16a34a",
                      }}
                    >
                      {issues > 0 ? (
                        <span>
                          {cnt.critical > 0 && <span style={{ color: "#dc2626" }}>{cnt.critical}✕</span>}
                          {cnt.critical > 0 && cnt.warn > 0 && " "}
                          {cnt.warn > 0 && <span style={{ color: "#d97706" }}>{cnt.warn}!</span>}
                        </span>
                      ) : (
                        <span style={{ color: "#22c55e" }}>✓</span>
                      )}
                    </td>
                  );
                })
              )}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: "8px 6px",
  textAlign: "left",
  fontWeight: 600,
  fontSize: 11,
  color: "#6b7280",
  whiteSpace: "nowrap",
  position: "sticky",
  top: 0,
  background: "#f9fafb",
  zIndex: 2,
};
