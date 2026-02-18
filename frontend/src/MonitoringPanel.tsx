/**
 * MonitoringPanel – Klinische Monitoring-Timeline pro Fall.
 *
 * Zeigt Sparklines in der Fallliste und Detail-Charts bei Klick:
 * - EKG-Zeitpunkte (als Marker auf Timeline)
 * - Neutrophile (Linie mit Grenzwert 2 G/l)
 * - Troponin (Linie)
 * - Grosses Blutbild (Zeitpunkte)
 *
 * Da wir aktuell nur den letzten Wert speichern,
 * zeigen wir eine kompakte Statusübersicht mit Timeline-Markern.
 * Bei voller KIS-Anbindung können echte Zeitreihen dargestellt werden.
 */
import React, { useState, useMemo } from "react";
import type { CaseSummary, ParameterStatus } from "./types";

/* ───── Monitoring-Parameter, die wir tracken ───── */
interface MonitoringItem {
  id: string;
  label: string;
  icon: string;
  getStatus: (params: ParameterStatus[]) => ParameterStatus | undefined;
  renderDetail: (c: CaseSummary) => React.ReactNode;
}

const MONITORING_ITEMS: MonitoringItem[] = [
  {
    id: "ekg",
    label: "EKG",
    icon: "💓",
    getStatus: (p) => p.find((x) => x.id === "ekg"),
    renderDetail: (c) => <EkgDetail params={c.parameter_status ?? []} />,
  },
  {
    id: "clozapin",
    label: "Clozapin-Monitoring",
    icon: "💊",
    getStatus: (p) => p.find((x) => x.id === "clozapin"),
    renderDetail: (c) => <ClozapinDetail params={c.parameter_status ?? []} />,
  },
  {
    id: "suicidality",
    label: "Suizidalität",
    icon: "⚠",
    getStatus: (p) => p.find((x) => x.id === "suicidality"),
    renderDetail: () => null,
  },
  {
    id: "isolation",
    label: "Isolation",
    icon: "🔒",
    getStatus: (p) => p.find((x) => x.id === "isolation"),
    renderDetail: () => null,
  },
];

/* ───── Farben ───── */
const STATUS_COLOR: Record<string, string> = {
  ok: "#22c55e",
  warn: "#f59e0b",
  critical: "#ef4444",
  na: "#d1d5db",
};

/* ───── Hauptkomponente ───── */
interface Props {
  cases: CaseSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
}

export default function MonitoringPanel({ cases, selectedCaseId, onSelectCase }: Props) {
  const [expandedCase, setExpandedCase] = useState<string | null>(null);

  /* Nur Fälle mit mindestens einem Monitoring-Parameter */
  const monitoredCases = useMemo(() => {
    return cases.filter((c) => {
      const params = c.parameter_status ?? [];
      return MONITORING_ITEMS.some((mi) => mi.getStatus(params) !== undefined);
    });
  }, [cases]);

  const selectedCase = useMemo(
    () => monitoredCases.find((c) => c.case_id === (expandedCase ?? selectedCaseId)),
    [monitoredCases, expandedCase, selectedCaseId]
  );

  return (
    <div>
      <h3 style={{ margin: "0 0 6px 0", fontSize: "1.1rem" }}>Klinisches Monitoring</h3>
      <p style={{ margin: "0 0 16px 0", fontSize: 12, color: "#6b7280" }}>
        Übersicht aktiver Monitoring-Parameter. Klick auf einen Fall für Details.
      </p>

      {monitoredCases.length === 0 ? (
        <div style={{ padding: 24, color: "#9ca3af", textAlign: "center", background: "#f9fafb", borderRadius: 8 }}>
          Keine Fälle mit aktivem Monitoring.
        </div>
      ) : (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
          {/* Linke Spalte: Fall-Liste mit Sparklines */}
          <div style={{ flex: "0 0 420px", maxHeight: 500, overflowY: "auto" }}>
            {monitoredCases.map((c) => {
              const params = c.parameter_status ?? [];
              const isExpanded = expandedCase === c.case_id;

              return (
                <div
                  key={c.case_id}
                  onClick={() => { setExpandedCase(isExpanded ? null : c.case_id); onSelectCase(c.case_id); }}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 8,
                    marginBottom: 6,
                    background: isExpanded ? "#eff6ff" : "#fff",
                    border: `1px solid ${isExpanded ? "#93c5fd" : "#e5e7eb"}`,
                    cursor: "pointer",
                    transition: "all 0.15s",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                    <div>
                      <span style={{ fontWeight: 700, fontFamily: "monospace", fontSize: 13 }}>{c.case_id}</span>
                      <span style={{ fontSize: 11, color: "#6b7280", marginLeft: 8 }}>{c.station_id}</span>
                    </div>
                    {/* Sparkline-artige Statusleiste */}
                    <div style={{ display: "flex", gap: 6 }}>
                      {MONITORING_ITEMS.map((mi) => {
                        const p = mi.getStatus(params);
                        if (!p) return null;
                        return (
                          <div
                            key={mi.id}
                            title={`${mi.label}: ${p.detail ?? "–"}`}
                            style={{ display: "flex", alignItems: "center", gap: 3 }}
                          >
                            <span style={{ fontSize: 12 }}>{mi.icon}</span>
                            <MiniSparkline status={p.status} />
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Mini-Zusammenfassung */}
                  <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                    {MONITORING_ITEMS.map((mi) => {
                      const p = mi.getStatus(params);
                      if (!p) return null;
                      return (
                        <span
                          key={mi.id}
                          style={{
                            fontSize: 10,
                            padding: "1px 6px",
                            borderRadius: 3,
                            fontWeight: 600,
                            background: `${STATUS_COLOR[p.status]}15`,
                            color: STATUS_COLOR[p.status],
                            border: `1px solid ${STATUS_COLOR[p.status]}44`,
                          }}
                        >
                          {mi.label}: {p.detail ?? "–"}
                        </span>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Rechte Spalte: Detail-Charts */}
          <div style={{ flex: 1, minWidth: 300 }}>
            {selectedCase ? (
              <div style={{ background: "#fff", border: "1px solid #e5e7eb", borderRadius: 8, padding: 16 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 12 }}>
                  Fall {selectedCase.case_id} – Monitoring-Details
                </div>

                {MONITORING_ITEMS.map((mi) => {
                  const p = mi.getStatus(selectedCase.parameter_status ?? []);
                  if (!p) return null;
                  return (
                    <div key={mi.id} style={{ marginBottom: 16 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <span style={{ fontSize: 16 }}>{mi.icon}</span>
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{mi.label}</span>
                        <StatusBadge status={p.status} detail={p.detail} />
                      </div>
                      <div style={{ paddingLeft: 24 }}>
                        {mi.renderDetail(selectedCase)}
                        {!mi.renderDetail(selectedCase) && p.detail && (
                          <div style={{ fontSize: 12, color: "#6b7280" }}>{p.detail}</div>
                        )}
                      </div>
                    </div>
                  );
                })}

                <div style={{ marginTop: 12, padding: 10, background: "#f1f5f9", borderRadius: 6, fontSize: 11, color: "#64748b" }}>
                  💡 Bei vollständiger KIS-Anbindung werden hier Zeitreihen-Charts mit
                  historischen Laborwerten (Neutrophile, Troponin, etc.) dargestellt.
                </div>
              </div>
            ) : (
              <div style={{ padding: 32, textAlign: "center", color: "#9ca3af", background: "#f9fafb", borderRadius: 8 }}>
                Wählen Sie einen Fall für Monitoring-Details.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ───── Mini-Sparkline (Status-Indikator als kleine Balken) ───── */
function MiniSparkline({ status }: { status: string }) {
  const color = STATUS_COLOR[status] ?? STATUS_COLOR.na;
  // 3 kleine Balken, der letzte zeigt den aktuellen Status
  const bars = status === "ok" ? [0.4, 0.6, 0.9] : status === "warn" ? [0.8, 0.6, 0.5] : status === "critical" ? [0.5, 0.7, 0.95] : [0.3, 0.3, 0.3];

  return (
    <svg width={20} height={14} viewBox="0 0 20 14">
      {bars.map((h, i) => (
        <rect
          key={i}
          x={i * 7}
          y={14 - h * 14}
          width={5}
          height={h * 14}
          rx={1}
          fill={i === bars.length - 1 ? color : `${color}66`}
        />
      ))}
    </svg>
  );
}

/* ───── Status-Badge ───── */
function StatusBadge({ status, detail }: { status: string; detail: string | null }) {
  const color = STATUS_COLOR[status];
  const labels: Record<string, string> = {
    ok: "OK",
    warn: "Warnung",
    critical: "Kritisch",
    na: "–",
  };
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        padding: "2px 6px",
        borderRadius: 999,
        background: `${color}20`,
        color: color,
        border: `1px solid ${color}44`,
      }}
    >
      {labels[status]}
    </span>
  );
}

/* ───── EKG-Detail ───── */
function EkgDetail({ params }: { params: ParameterStatus[] }) {
  const p = params.find((x) => x.id === "ekg");
  if (!p) return null;

  return (
    <div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <TimelineBar label="Eintritts-EKG" status={p.status === "warn" && p.detail?.includes("ET-EKG") ? "warn" : p.status === "ok" ? "ok" : "na"} />
        <TimelineBar label="Letzte Befundung" status={p.status === "critical" ? "critical" : p.status === "ok" ? "ok" : "na"} />
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
        {p.detail ?? "Keine Daten verfügbar."}
      </div>
    </div>
  );
}

/* ───── Clozapin-Detail ───── */
function ClozapinDetail({ params }: { params: ParameterStatus[] }) {
  const p = params.find((x) => x.id === "clozapin");
  if (!p) return null;

  const isCritical = p.status === "critical";
  const neutrophilAlert = p.detail?.includes("Neutrophile");

  return (
    <div>
      {/* Simulated gauge for Neutrophile */}
      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 4 }}>Neutrophile (Grenzwert: 2.0 G/l)</div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ flex: 1, height: 8, background: "#f3f4f6", borderRadius: 4, overflow: "hidden", position: "relative" }}>
            <div style={{
              position: "absolute", left: 0, top: 0, bottom: 0, borderRadius: 4,
              width: isCritical && neutrophilAlert ? "30%" : "70%",
              background: isCritical && neutrophilAlert
                ? "linear-gradient(90deg, #ef4444, #f87171)"
                : "linear-gradient(90deg, #22c55e, #4ade80)",
            }} />
            {/* Grenzwert-Markierung bei 40% (=2 G/l von 5 G/l Skala) */}
            <div style={{
              position: "absolute", left: "40%", top: -2, bottom: -2,
              width: 2, background: "#dc2626",
            }} />
          </div>
          <span style={{
            fontSize: 12, fontWeight: 700,
            color: isCritical && neutrophilAlert ? "#dc2626" : "#16a34a",
          }}>
            {isCritical && neutrophilAlert ? "<2.0" : "≥2.0"} G/l
          </span>
        </div>
      </div>

      {/* Status-Zeilen */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <TimelineBar
          label="Grosses Blutbild"
          status={p.detail?.includes("BB") ? "warn" : "ok"}
        />
        <TimelineBar
          label="Troponin"
          status={p.detail?.includes("Troponin") ? "warn" : "ok"}
        />
      </div>
      <div style={{ fontSize: 11, color: "#6b7280", marginTop: 6 }}>
        {p.detail ?? "Monitoring aktuell."}
      </div>
    </div>
  );
}

/* ───── Timeline-Bar (einfache visuelle Status-Anzeige) ───── */
function TimelineBar({ label, status }: { label: string; status: string }) {
  const color = STATUS_COLOR[status];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{
        width: 8, height: 8, borderRadius: "50%", background: color, flexShrink: 0,
      }} />
      <span style={{ fontSize: 11, color: "#374151" }}>{label}</span>
    </div>
  );
}
