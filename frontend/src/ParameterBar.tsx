/**
 * ParameterBar – Kompakte Parameterleiste pro Fall.
 *
 * Zeigt kleine farbcodierte Badges pro Parameter:
 *   ● grün  = ok
 *   ● gelb  = warn
 *   ● rot   = critical
 *   ● grau  = n/a
 *
 * Beim Hover erscheint ein Tooltip mit Detail-Info.
 * Die Badges sind nach Gruppe (completeness / medical) geordnet.
 */

import { useState } from "react";
import type { ParameterStatus } from "./types";

const STATUS_COLORS: Record<string, string> = {
  ok: "#22c55e",
  warn: "#f59e0b",
  critical: "#ef4444",
  na: "#d1d5db",
};

const STATUS_BG: Record<string, string> = {
  ok: "#f0fdf4",
  warn: "#fffbeb",
  critical: "#fef2f2",
  na: "#f9fafb",
};

interface Props {
  parameters: ParameterStatus[];
  compact?: boolean;         // nur Punkte (in Fallliste)
  showGroupLabels?: boolean; // Gruppentitel anzeigen (im Detail)
  filterGroup?: "completeness" | "medical" | "all";
}

export default function ParameterBar({
  parameters,
  compact = true,
  showGroupLabels = false,
  filterGroup = "all",
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const filtered =
    filterGroup === "all"
      ? parameters
      : parameters.filter((p) => p.group === filterGroup);

  if (!filtered.length) return null;

  // Sortierung: critical zuerst, dann warn, dann ok/na
  const ORDER: Record<string, number> = { critical: 0, warn: 1, ok: 2, na: 3 };
  const sorted = [...filtered].sort((a, b) => (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9));

  if (compact) {
    return (
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 3,
          marginTop: 5,
        }}
      >
        {sorted.map((p) => (
          <div
            key={p.id}
            onMouseEnter={() => setHoveredId(p.id)}
            onMouseLeave={() => setHoveredId(null)}
            style={{ position: "relative", display: "inline-flex" }}
          >
            <div
              title={`${p.label}: ${p.detail ?? "–"}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 3,
                padding: "1px 5px",
                borderRadius: 4,
                fontSize: 10,
                fontWeight: 600,
                lineHeight: "16px",
                background: STATUS_BG[p.status],
                color: p.status === "na" ? "#9ca3af" : "#333",
                border: `1px solid ${STATUS_COLORS[p.status]}`,
                cursor: "default",
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: STATUS_COLORS[p.status],
                  flexShrink: 0,
                }}
              />
              {p.label}
            </div>
            {hoveredId === p.id && p.detail && (
              <div
                style={{
                  position: "absolute",
                  bottom: "100%",
                  left: "50%",
                  transform: "translateX(-50%)",
                  marginBottom: 4,
                  padding: "4px 8px",
                  background: "#1f2937",
                  color: "white",
                  fontSize: 11,
                  borderRadius: 4,
                  whiteSpace: "nowrap",
                  zIndex: 100,
                  pointerEvents: "none",
                }}
              >
                {p.detail}
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  // Expanded mode (Detail-Ansicht)
  const groups: Record<string, ParameterStatus[]> = {};
  for (const p of sorted) {
    const g = p.group;
    if (!groups[g]) groups[g] = [];
    groups[g].push(p);
  }

  const GROUP_LABELS: Record<string, string> = {
    completeness: "Vollständigkeit",
    medical: "Klinisch",
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {Object.entries(groups).map(([group, params]) => (
        <div key={group}>
          {showGroupLabels && (
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#6b7280",
                textTransform: "uppercase",
                letterSpacing: 0.5,
                marginBottom: 4,
              }}
            >
              {GROUP_LABELS[group] ?? group}
            </div>
          )}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {params.map((p) => (
              <div
                key={p.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  borderRadius: 6,
                  background: STATUS_BG[p.status],
                  border: `1px solid ${STATUS_COLORS[p.status]}`,
                  fontSize: 12,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: STATUS_COLORS[p.status],
                    flexShrink: 0,
                  }}
                />
                <span style={{ fontWeight: 600 }}>{p.label}</span>
                {p.detail && (
                  <span style={{ color: "#6b7280", fontSize: 11 }}>
                    {p.detail}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
