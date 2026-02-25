/**
 * CaseTable – Sortierbare Fallliste als Tabelle.
 *
 * Features:
 * - Klickbare Spaltenköpfe zum Sortieren (↑↓)
 * - Kompakte Parameter-Badges pro Zeile
 * - Mini-Sparklines für Monitoring-Werte
 * - Farbcodierte Severity-Indikatoren
 * - Klick auf Zeile öffnet Detail
 */
import { useState, useMemo } from "react";
import type { CaseSummary, ParameterStatus, Severity } from "./types";

/* ───── Sortierung ───── */
type SortKey =
  | "case_id"
  | "station_id"
  | "admission_date"
  | "discharge_date"
  | "severity"
  | "critical_count"
  | "days";
type SortDir = "asc" | "desc";

const SEV_ORDER: Record<Severity, number> = { CRITICAL: 0, WARN: 1, OK: 2 };

function cmpVal(a: CaseSummary, b: CaseSummary, key: SortKey): number {
  switch (key) {
    case "case_id":
      return a.case_id.localeCompare(b.case_id);
    case "station_id":
      return a.station_id.localeCompare(b.station_id);
    case "admission_date":
      return a.admission_date.localeCompare(b.admission_date);
    case "discharge_date": {
      const da = a.discharge_date ?? "9999";
      const db = b.discharge_date ?? "9999";
      return da.localeCompare(db);
    }
    case "severity":
      return SEV_ORDER[a.severity] - SEV_ORDER[b.severity];
    case "critical_count":
      return (b.critical_count ?? 0) - (a.critical_count ?? 0);
    case "days": {
      const daysA = daysSince(a.admission_date);
      const daysB = daysSince(b.admission_date);
      return daysB - daysA;
    }
    default:
      return 0;
  }
}

function daysSince(isoDate: string): number {
  const d = new Date(isoDate);
  const now = new Date();
  return Math.floor((now.getTime() - d.getTime()) / 86400000);
}

/* ───── Farben ───── */
const STATUS_DOT: Record<string, string> = {
  ok: "#22c55e",
  warn: "#f59e0b",
  critical: "#ef4444",
  na: "#d1d5db",
};

const SEV_BG: Record<Severity, string> = {
  CRITICAL: "#fef2f2",
  WARN: "#fffbeb",
  OK: "#f0fdf4",
};

const SEV_BADGE: Record<Severity, { bg: string; color: string; label: string }> = {
  CRITICAL: { bg: "#ef4444", color: "#fff", label: "Kritisch" },
  WARN: { bg: "#f59e0b", color: "#fff", label: "Warnung" },
  OK: { bg: "#22c55e", color: "#fff", label: "OK" },
};

/* ───── Spalten-Definition ───── */
const COLUMNS: { key: SortKey; label: string; width: string; align?: string }[] = [
  { key: "case_id", label: "Fall-Nr.", width: "100px" },
  { key: "station_id", label: "Station", width: "70px" },
  { key: "admission_date", label: "Eintritt", width: "95px" },
  { key: "discharge_date", label: "Austritt", width: "95px" },
  { key: "days", label: "Tage", width: "55px", align: "right" },
  { key: "severity", label: "Status", width: "90px" },
];

/* ───── Komponente ───── */
interface Props {
  cases: CaseSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  parameterFilter?: "all" | "completeness" | "medical";
}

export default function CaseTable({ cases, selectedCaseId, onSelectCase, parameterFilter = "all" }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("severity");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const sorted = useMemo(() => {
    const arr = [...cases];
    arr.sort((a, b) => {
      const c = cmpVal(a, b, sortKey);
      return sortDir === "asc" ? c : -c;
    });
    return arr;
  }, [cases, sortKey, sortDir]);

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid #e5e7eb", background: "#f9fafb" }}>
            {COLUMNS.map((col) => (
              <th
                key={col.key}
                onClick={() => toggleSort(col.key)}
                style={{
                  padding: "10px 8px",
                  textAlign: (col.align as any) || "left",
                  fontWeight: 600,
                  fontSize: 11,
                  color: "#6b7280",
                  textTransform: "uppercase",
                  letterSpacing: 0.5,
                  cursor: "pointer",
                  userSelect: "none",
                  whiteSpace: "nowrap",
                  width: col.width,
                  position: "sticky",
                  top: 0,
                  background: "#f9fafb",
                  zIndex: 2,
                }}
              >
                {col.label}{" "}
                {sortKey === col.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
              </th>
            ))}
            <th
              style={{
                padding: "10px 8px",
                textAlign: "left",
                fontWeight: 600,
                fontSize: 11,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: 0.5,
                position: "sticky",
                top: 0,
                background: "#f9fafb",
                zIndex: 2,
              }}
            >
              Parameter
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={COLUMNS.length + 1} style={{ padding: 24, color: "#9ca3af", textAlign: "center" }}>
                Keine Fälle für diese Station.
              </td>
            </tr>
          ) : (
            sorted.map((c) => {
              const isSelected = selectedCaseId === c.case_id;
              const days = daysSince(c.admission_date);
              // Use category-specific severity when filtered
              const effectiveSev = parameterFilter === "completeness"
                ? (c.completeness_severity ?? c.severity)
                : parameterFilter === "medical"
                  ? (c.medical_severity ?? c.severity)
                  : c.severity;
              const effectiveCC = parameterFilter === "completeness"
                ? (c.completeness_critical ?? 0)
                : parameterFilter === "medical"
                  ? (c.medical_critical ?? 0)
                  : (c.critical_count ?? 0);
              const effectiveWC = parameterFilter === "completeness"
                ? (c.completeness_warn ?? 0)
                : parameterFilter === "medical"
                  ? (c.medical_warn ?? 0)
                  : (c.warn_count ?? 0);
              const sev = SEV_BADGE[effectiveSev];
              const params = c.parameter_status ?? [];
              const filtered =
                parameterFilter === "all" ? params : params.filter((p) => p.group === parameterFilter);

              return (
                <tr
                  key={c.case_id}
                  onClick={() => onSelectCase(c.case_id)}
                  style={{
                    borderBottom: "1px solid #f3f4f6",
                    cursor: "pointer",
                    background: isSelected ? "#eff6ff" : undefined,
                    transition: "background 0.1s",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "#f9fafb";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) e.currentTarget.style.background = "";
                  }}
                >
                  {/* Fall-Nr */}
                  <td style={{ padding: "10px 8px", fontWeight: 700, fontFamily: "monospace", fontSize: 13 }}>
                    {c.case_id}
                  </td>

                  {/* Station */}
                  <td style={{ padding: "10px 8px" }}>
                    <span style={{ fontWeight: 600 }}>{c.station_id}</span>
                  </td>

                  {/* Eintritt */}
                  <td style={{ padding: "10px 8px", fontSize: 12, color: "#374151" }}>
                    {c.admission_date}
                  </td>

                  {/* Austritt */}
                  <td style={{ padding: "10px 8px", fontSize: 12 }}>
                    {c.discharge_date ? (
                      <span style={{ color: "#374151" }}>{c.discharge_date}</span>
                    ) : (
                      <span style={{ color: "#2563eb", fontWeight: 600, fontSize: 11 }}>offen</span>
                    )}
                  </td>

                  {/* Tage */}
                  <td style={{ padding: "10px 8px", textAlign: "right", fontFamily: "monospace", fontSize: 12 }}>
                    {days}d
                  </td>

                  {/* Status */}
                  <td style={{ padding: "10px 8px" }}>
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "2px 8px",
                        borderRadius: 999,
                        fontSize: 11,
                        fontWeight: 700,
                        background: sev.bg,
                        color: sev.color,
                      }}
                    >
                      {effectiveSev === "CRITICAL" ? "‼" : effectiveSev === "WARN" ? "⚠" : "✓"}
                      {" "}{effectiveCC + effectiveWC > 0
                        ? `${effectiveCC}/${effectiveWC}`
                        : "OK"}
                    </span>
                  </td>

                  {/* Parameter-Badges */}
                  <td style={{ padding: "8px 8px" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                      {filtered.map((p) => (
                        <ParamDot key={p.id} p={p} />
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

/* ───── Parameter-Dot mit Tooltip ───── */
function ParamDot({ p }: { p: ParameterStatus }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: "relative", display: "inline-flex" }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 2,
          padding: "1px 5px",
          borderRadius: 3,
          fontSize: 10,
          fontWeight: 600,
          lineHeight: "16px",
          background: p.status === "na" ? "#f3f4f6" : `${STATUS_DOT[p.status]}18`,
          color: p.status === "na" ? "#9ca3af" : STATUS_DOT[p.status],
          border: `1px solid ${STATUS_DOT[p.status]}44`,
          whiteSpace: "nowrap",
          cursor: "default",
        }}
      >
        <span
          style={{
            width: 5,
            height: 5,
            borderRadius: "50%",
            background: STATUS_DOT[p.status],
            flexShrink: 0,
          }}
        />
        {p.label}
      </div>
      {hovered && p.detail && (
        <div
          style={{
            position: "absolute",
            bottom: "calc(100% + 4px)",
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
          {p.detail}
        </div>
      )}
    </div>
  );
}
