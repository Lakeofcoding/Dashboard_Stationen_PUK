/**
 * ParameterGroupPanel – Hierarchische, aufklappbare Parametergruppen mit integriertem ACK/SHIFT.
 *
 * Ersetzt die separate Alerts-Liste: jedes Parameter-Item mit Problem hat
 * einen expandierbaren Detailbereich mit Erklärung + Aktions-Buttons.
 *
 * Quittierte/geschobene Items verschwinden NICHT, sondern zeigen ihren Status.
 * Beim nächsten Datenrefresh: condition_hash-Änderung → ACK invalidiert → Item wieder aktiv.
 */

import { useState, useMemo } from "react";
import type { ParameterGroup, ParameterStatus, Severity } from "./types";

/* ───── Farben ───── */
const SEV = {
  CRITICAL: { bg: "#fef2f2", border: "#fca5a5", dot: "#ef4444", text: "#991b1b", pill: "#ef4444", pillText: "#fff" },
  WARN:     { bg: "#fffbeb", border: "#fcd34d", dot: "#f59e0b", text: "#92400e", pill: "#f59e0b", pillText: "#fff" },
  OK:       { bg: "#f0fdf4", border: "#bbf7d0", dot: "#22c55e", text: "#166534", pill: "#22c55e", pillText: "#fff" },
};

const ITEM_STATUS: Record<string, { dot: string; bg: string; border: string; text: string }> = {
  ok:       { dot: "#22c55e", bg: "#f0fdf4", border: "#bbf7d0", text: "#166534" },
  warn:     { dot: "#f59e0b", bg: "#fffbeb", border: "#fcd34d", text: "#92400e" },
  critical: { dot: "#ef4444", bg: "#fef2f2", border: "#fca5a5", text: "#991b1b" },
  na:       { dot: "#d1d5db", bg: "#f9fafb", border: "#e5e7eb", text: "#6b7280" },
};

const GROUP_ICONS: Record<string, string> = {
  spiges_person: "👤",
  spiges_eintritt: "🚪",
  spiges_austritt: "🚶",
  spiges_behandlung: "💊",
  mb_minimaldaten: "📋",
  fu: "⚖️",
  honos: "📊",
  bscl: "📝",
  bfs: "📦",
  dok_austritt: "📄",
  behandlungsplan: "📑",
  langlieger: "🏥",
  klinisch: "🩺",
};

type ShiftReason = { id: number; code: string; label: string; description: string | null };

/* ═══════════════════════════════════════════════════════════════════ */
/* Compact Group Pills (für CaseTable)                                */
/* ═══════════════════════════════════════════════════════════════════ */

interface CompactProps {
  groups: ParameterGroup[];
  maxVisible?: number;
}

export function CompactGroupPills({ groups, maxVisible = 12 }: CompactProps) {
  const [hovered, setHovered] = useState<string | null>(null);
  const ORDER: Record<Severity, number> = { CRITICAL: 0, WARN: 1, OK: 2 };
  const sorted = useMemo(() =>
    [...groups].sort((a, b) => ORDER[a.severity] - ORDER[b.severity]),
    [groups]
  );
  const visible = sorted.slice(0, maxVisible);
  const overflow = sorted.length - maxVisible;

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
      {visible.map((g) => {
        const s = SEV[g.severity];
        const icon = GROUP_ICONS[g.key] ?? "📁";
        const openCount = g.items.filter(i =>
          (i.status === "critical" || i.status === "warn") && !i.ack
        ).length;
        const ackedCount = g.items.filter(i =>
          (i.status === "critical" || i.status === "warn") && i.ack
        ).length;
        return (
          <div key={g.key}
            onMouseEnter={() => setHovered(g.key)}
            onMouseLeave={() => setHovered(null)}
            style={{ position: "relative", display: "inline-flex" }}
          >
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 3,
              padding: "1px 6px", borderRadius: 4, fontSize: 10, fontWeight: 600,
              lineHeight: "16px", background: s.bg, color: s.text,
              border: `1px solid ${s.border}`, cursor: "default", whiteSpace: "nowrap",
            }}>
              <span style={{ fontSize: 9 }}>{icon}</span>
              {g.label}
              {openCount > 0 && (
                <span style={{
                  fontSize: 9, fontWeight: 800, color: s.pillText, background: s.pill,
                  borderRadius: 3, padding: "0 3px", lineHeight: "14px", minWidth: 14, textAlign: "center",
                }}>{openCount}</span>
              )}
              {ackedCount > 0 && (
                <span style={{
                  fontSize: 9, fontWeight: 700, color: "#fff", background: "#9ca3af",
                  borderRadius: 3, padding: "0 3px", lineHeight: "14px",
                }}>✓{ackedCount}</span>
              )}
            </div>
            {hovered === g.key && (
              <div style={{
                position: "absolute", bottom: "100%", left: "50%", transform: "translateX(-50%)",
                marginBottom: 4, padding: "6px 10px", background: "#1f2937", color: "#fff",
                fontSize: 11, borderRadius: 6, whiteSpace: "nowrap", zIndex: 100,
                pointerEvents: "none", maxWidth: 300,
              }}>
                <div style={{ fontWeight: 700, marginBottom: 2 }}>{g.label}</div>
                {g.items.filter(i => i.status !== "ok" && i.status !== "na").map(item => (
                  <div key={item.id} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                    <span style={{
                      width: 5, height: 5, borderRadius: "50%",
                      background: item.ack ? "#9ca3af" : (ITEM_STATUS[item.status]?.dot ?? "#d1d5db"),
                      flexShrink: 0,
                    }} />
                    <span style={{ textDecoration: item.ack ? "line-through" : "none", opacity: item.ack ? 0.7 : 1 }}>
                      {item.label}: {item.detail ?? "–"}
                    </span>
                    {item.ack && <span style={{ fontSize: 9, color: "#9ca3af" }}>({item.ack.state})</span>}
                  </div>
                ))}
                {g.items.every(i => i.status === "ok" || i.status === "na") && (
                  <div style={{ color: "#86efac" }}>✓ Alles OK</div>
                )}
              </div>
            )}
          </div>
        );
      })}
      {overflow > 0 && (
        <span style={{ fontSize: 10, color: "#9ca3af", padding: "1px 4px" }}>+{overflow}</span>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ */
/* Full Accordion mit Inline-ACK (für DetailPanel)                    */
/* ═══════════════════════════════════════════════════════════════════ */

interface AccordionProps {
  groups: ParameterGroup[];
  categoryFilter?: "all" | "completeness" | "medical";
  // ACK/SHIFT handlers
  canAck?: boolean;
  caseId?: string;
  shiftReasons?: ShiftReason[];
  onAckRule?: (caseId: string, ruleId: string) => Promise<void>;
  onShiftRule?: (caseId: string, ruleId: string, shiftCode: string) => Promise<void>;
  onUndoAck?: (caseId: string, ruleId: string) => Promise<void>;
  onError?: (msg: string) => void;
}

export default function ParameterGroupPanel({
  groups,
  categoryFilter = "all",
  canAck = false,
  caseId,
  shiftReasons = [],
  onAckRule,
  onShiftRule,
  onUndoAck,
  onError,
}: AccordionProps) {
  const filtered = useMemo(() => {
    if (categoryFilter === "all") return groups;
    return groups
      .filter(g => g.items.some(item => item.group === categoryFilter))
      .map(g => ({ ...g, items: g.items.filter(item => item.group === categoryFilter) }));
  }, [groups, categoryFilter]);

  // Auto-expand groups with unresolved issues
  const initialExpanded = useMemo(() => {
    const set = new Set<string>();
    for (const g of filtered) {
      if (g.items.some(i => (i.status === "critical" || i.status === "warn") && !i.ack))
        set.add(g.key);
    }
    return set;
  }, [filtered]);

  const [expanded, setExpanded] = useState<Set<string>>(initialExpanded);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [shiftSelections, setShiftSelections] = useState<Record<string, string>>({});

  const toggle = (key: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(filtered.map(g => g.key)));
  const collapseAll = () => { setExpanded(new Set()); setExpandedItem(null); };

  if (!filtered.length) return null;

  const openProblems = filtered.reduce((sum, g) =>
    sum + g.items.filter(i => (i.status === "critical" || i.status === "warn") && !i.ack).length, 0);
  const ackedProblems = filtered.reduce((sum, g) =>
    sum + g.items.filter(i => (i.status === "critical" || i.status === "warn") && i.ack).length, 0);

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", display: "flex", alignItems: "center", gap: 8 }}>
          Parameter-Übersicht
          {openProblems > 0 && (
            <span style={{
              fontSize: 10, fontWeight: 800, background: "#ef4444", color: "#fff",
              borderRadius: 10, padding: "1px 7px",
            }}>{openProblems} offen</span>
          )}
          {ackedProblems > 0 && (
            <span style={{
              fontSize: 10, fontWeight: 700, background: "#d1d5db", color: "#374151",
              borderRadius: 10, padding: "1px 7px",
            }}>✓ {ackedProblems} bearbeitet</span>
          )}
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={expandAll} style={btnStyle}>Alle öffnen</button>
          <button onClick={collapseAll} style={btnStyle}>Alle schliessen</button>
        </div>
      </div>

      {/* Groups */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {filtered.map(g => {
          const isOpen = expanded.has(g.key);
          const icon = GROUP_ICONS[g.key] ?? "📁";
          const openItems = g.items.filter(i => (i.status === "critical" || i.status === "warn") && !i.ack);
          const ackedItems = g.items.filter(i => (i.status === "critical" || i.status === "warn") && i.ack);
          const okItems = g.items.filter(i => i.status === "ok" || i.status === "na");

          // Effective severity: if all problems acked → show as OK-ish
          const effectiveSev = openItems.length > 0
            ? g.severity
            : ackedItems.length > 0 ? "OK" : g.severity;
          const s = SEV[effectiveSev];

          return (
            <div key={g.key} style={{
              borderRadius: 8, border: `1px solid ${s.border}`,
              background: isOpen ? "#fff" : s.bg, overflow: "hidden",
              transition: "all 0.15s ease",
            }}>
              {/* Group header */}
              <div onClick={() => toggle(g.key)} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "8px 12px", cursor: "pointer", background: s.bg, userSelect: "none",
              }}>
                <span style={{
                  fontSize: 10, color: "#9ca3af",
                  transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                  transition: "transform 0.15s", flexShrink: 0,
                }}>▶</span>
                <span style={{ fontSize: 13, flexShrink: 0 }}>{icon}</span>
                <span style={{ fontWeight: 700, fontSize: 12, color: "#374151", flex: 1 }}>{g.label}</span>

                {/* Counters */}
                <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  {openItems.length > 0 && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "1px 8px", borderRadius: 10,
                      background: SEV[g.severity].pill, color: SEV[g.severity].pillText,
                    }}>
                      {g.severity === "CRITICAL" ? "‼" : "⚠"} {openItems.length}
                    </span>
                  )}
                  {ackedItems.length > 0 && (
                    <span style={{
                      fontSize: 10, fontWeight: 600, padding: "1px 8px", borderRadius: 10,
                      background: "#e5e7eb", color: "#6b7280",
                    }}>✓ {ackedItems.length}</span>
                  )}
                  {openItems.length === 0 && ackedItems.length === 0 && (
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: "1px 8px", borderRadius: 10,
                      background: "#22c55e", color: "#fff",
                    }}>✓ {g.items.length}/{g.items.length}</span>
                  )}
                </div>
              </div>

              {/* Expanded content */}
              {isOpen && (
                <div style={{ padding: "4px 12px 10px 36px", display: "flex", flexDirection: "column", gap: 3 }}>
                  {/* Open problems first */}
                  {openItems.map(item => (
                    <ItemRow key={item.id} item={item} isExpanded={expandedItem === item.id}
                      onToggle={() => setExpandedItem(expandedItem === item.id ? null : item.id)}
                      canAck={canAck} caseId={caseId} shiftReasons={shiftReasons}
                      shiftVal={shiftSelections[item.id] ?? ""}
                      onShiftSelect={v => setShiftSelections(p => ({ ...p, [item.id]: v }))}
                      onAckRule={async (cid, rid) => { await onAckRule?.(cid, rid); setExpandedItem(null); }}
                      onShiftRule={async (cid, rid, sc) => { await onShiftRule?.(cid, rid, sc); setExpandedItem(null); }}
                      onUndoAck={onUndoAck}
                      onError={onError}
                    />
                  ))}
                  {/* Acked problems (dimmed, with badge) */}
                  {ackedItems.map(item => (
                    <ItemRow key={item.id} item={item} acked isExpanded={expandedItem === item.id}
                      onToggle={() => setExpandedItem(expandedItem === item.id ? null : item.id)}
                      canAck={canAck} caseId={caseId} shiftReasons={shiftReasons}
                      shiftVal={shiftSelections[item.id] ?? ""}
                      onShiftSelect={v => setShiftSelections(p => ({ ...p, [item.id]: v }))}
                      onAckRule={async (cid, rid) => { await onAckRule?.(cid, rid); setExpandedItem(null); }}
                      onShiftRule={async (cid, rid, sc) => { await onShiftRule?.(cid, rid, sc); setExpandedItem(null); }}
                      onUndoAck={onUndoAck}
                      onError={onError}
                    />
                  ))}
                  {/* OK items (collapsed summary) */}
                  {okItems.length > 0 && (
                    <div style={{
                      display: "flex", flexWrap: "wrap", gap: 4, paddingTop: 2,
                      borderTop: openItems.length + ackedItems.length > 0 ? "1px solid #e5e7eb" : "none",
                      marginTop: openItems.length + ackedItems.length > 0 ? 4 : 0,
                    }}>
                      {okItems.map(item => (
                        <span key={item.id} style={{
                          fontSize: 11, color: "#6b7280", display: "inline-flex",
                          alignItems: "center", gap: 3, opacity: 0.6,
                        }}>
                          <span style={{
                            width: 5, height: 5, borderRadius: "50%", background: "#22c55e", flexShrink: 0,
                          }} />
                          {item.label}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ */
/* Item Row — Expandierbar mit Inline-ACK/SHIFT                       */
/* ═══════════════════════════════════════════════════════════════════ */

function ackLabel(group: string): string {
  return group === "completeness" ? "Behoben" : "Gesehen";
}

interface ItemRowProps {
  item: ParameterStatus;
  acked?: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  canAck?: boolean;
  caseId?: string;
  shiftReasons?: ShiftReason[];
  shiftVal: string;
  onShiftSelect: (v: string) => void;
  onAckRule?: (caseId: string, ruleId: string) => Promise<void>;
  onShiftRule?: (caseId: string, ruleId: string, shiftCode: string) => Promise<void>;
  onUndoAck?: (caseId: string, ruleId: string) => Promise<void>;
  onError?: (msg: string) => void;
}

function ItemRow({
  item, acked = false, isExpanded, onToggle,
  canAck, caseId, shiftReasons = [], shiftVal, onShiftSelect,
  onAckRule, onShiftRule, onUndoAck, onError,
}: ItemRowProps) {
  const [hovered, setHovered] = useState(false);
  const colors = ITEM_STATUS[item.status] ?? ITEM_STATUS.na;
  // Alle Warn/Critical Items sind klickbar (auch ohne rule_id → zeigt zumindest Detail)
  const isProblem = item.status === "warn" || item.status === "critical";
  const hasRuleActions = !!item.rule_id && isProblem;

  return (
    <div style={{
      borderRadius: 8,
      border: `1px solid ${acked ? "#d1d5db" : isExpanded ? colors.dot : colors.border}`,
      background: acked ? "#f9fafb" : isExpanded ? "#fff" : colors.bg,
      opacity: acked && !isExpanded ? 0.65 : 1,
      overflow: "hidden",
      transition: "all 0.15s",
      // Linker Akzentstreifen für klickbare Items
      borderLeft: isProblem ? `3px solid ${acked ? "#9ca3af" : colors.dot}` : `1px solid ${colors.border}`,
    }}>
      {/* ── Hauptzeile (klickbar) ── */}
      <div
        onClick={isProblem ? onToggle : undefined}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "7px 12px 7px 10px",
          cursor: isProblem ? "pointer" : "default",
          fontSize: 12,
          background: isProblem && hovered && !isExpanded
            ? `${colors.dot}12`
            : "transparent",
          transition: "background 0.1s",
        }}
      >
        {/* Chevron (nur bei Problemen) */}
        {isProblem ? (
          <span style={{
            fontSize: 11, color: colors.dot, fontWeight: 700,
            transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: "transform 0.15s", flexShrink: 0,
            width: 14, textAlign: "center",
          }}>▶</span>
        ) : (
          <span style={{
            width: 7, height: 7, borderRadius: "50%",
            background: colors.dot, flexShrink: 0, marginLeft: 3, marginRight: 4,
          }} />
        )}

        {/* Label */}
        <span style={{
          fontWeight: 600,
          color: acked ? "#9ca3af" : colors.text,
          textDecoration: acked && item.ack?.state === "ACK" ? "line-through" : "none",
          minWidth: 110,
        }}>
          {item.label}
        </span>

        {/* Detail */}
        <span style={{ color: "#6b7280", fontSize: 11, flex: 1 }}>
          {item.detail ?? "–"}
        </span>

        {/* ACK/SHIFT badge */}
        {item.ack && (
          <span style={{
            fontSize: 9, fontWeight: 700, padding: "2px 8px", borderRadius: 10,
            background: item.ack.state === "ACK" ? "#d1fae5" : "#e0e7ff",
            color: item.ack.state === "ACK" ? "#065f46" : "#3730a3",
            whiteSpace: "nowrap",
          }}>
            {item.ack.state === "ACK" ? "✓ " + ackLabel(item.group) : "⏭ Erinnert"}
            {item.ack.shift_code ? ` (${item.ack.shift_code})` : ""}
          </span>
        )}

        {/* Klick-Hinweis bei Hover */}
        {isProblem && hovered && !isExpanded && !item.ack && (
          <span style={{
            fontSize: 9, color: colors.dot, fontWeight: 600,
            whiteSpace: "nowrap", opacity: 0.8,
          }}>
            Details →
          </span>
        )}
      </div>

      {/* ── Expandierter Bereich ── */}
      {isExpanded && isProblem && (
        <div style={{
          padding: "10px 14px 12px 28px",
          borderTop: `1px solid ${colors.border}`,
          background: `${colors.bg}`,
        }}>
          {/* Erklärung */}
          {item.explanation ? (
            <div style={{
              fontSize: 12, color: "#374151", marginBottom: 10, lineHeight: 1.5,
              padding: "8px 12px", background: "#fff", borderRadius: 6,
              border: "1px solid #e5e7eb",
            }}>
              {item.explanation}
            </div>
          ) : (
            <div style={{
              fontSize: 11, color: "#9ca3af", marginBottom: 10, fontStyle: "italic",
            }}>
              {item.detail ?? "Keine zusätzliche Erklärung verfügbar."}
            </div>
          )}

          {/* Regel-ID (dezent) */}
          {item.rule_id && (
            <div style={{
              fontSize: 9, color: "#9ca3af", marginBottom: 10, fontFamily: "monospace",
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{
                background: "#f3f4f6", padding: "1px 6px", borderRadius: 3,
              }}>
                {item.rule_id}
              </span>
              <span>·</span>
              <span>{item.group === "completeness" ? "📋 Dokumentation" : "🩺 Klinisch"}</span>
            </div>
          )}

          {/* Bereits quittiert? → Info anzeigen + Undo */}
          {item.ack && (
            <div style={{
              fontSize: 11, color: "#6b7280", marginBottom: 10,
              padding: "6px 10px", background: item.ack.state === "ACK" ? "#d1fae5" : "#e0e7ff",
              borderRadius: 6, display: "flex", alignItems: "center", gap: 6,
            }}>
              <span style={{ fontSize: 14 }}>{item.ack.state === "ACK" ? "✓" : "⏭"}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, color: "#374151" }}>
                  {item.ack.state === "ACK"
                    ? `Als "${ackLabel(item.group)}" markiert`
                    : `Erinnert (${item.ack.shift_code ?? "–"})`}
                </div>
                <div style={{ fontSize: 10, color: "#6b7280" }}>
                  {fmtTs(item.ack.ts)} · Wird bei Datenänderung automatisch reaktiviert
                </div>
              </div>
              {/* Rückgängig-Button */}
              {canAck && caseId && item.rule_id && onUndoAck && (
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (!confirm("Quittierung rückgängig machen?")) return;
                    try { await onUndoAck(caseId, item.rule_id!); }
                    catch (err: any) { onError?.(err?.message ?? String(err)); }
                  }}
                  style={{
                    padding: "3px 8px", fontSize: 10, borderRadius: 4, fontWeight: 600,
                    border: "1px solid #fca5a5", background: "#fff", color: "#dc2626",
                    cursor: "pointer", whiteSpace: "nowrap",
                  }}
                  title="Quittierung rückgängig machen"
                >
                  ↩ Rückgängig
                </button>
              )}
            </div>
          )}

          {/* Aktions-Buttons — immer sichtbar, bei fehlender Berechtigung disabled */}
          {hasRuleActions && caseId && !item.ack && (
            <div style={{
              display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
              padding: "8px 0 0",
              borderTop: "1px solid #e5e7eb",
            }}>
              {/* SHIFT: Erinnern */}
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <select
                  disabled={!canAck}
                  value={shiftVal}
                  onChange={e => { if (!canAck) { onError?.("Keine Berechtigung für Quittierungen/Schiebungen."); return; } onShiftSelect(e.target.value); }}
                  style={{
                    padding: "5px 8px", borderRadius: 6, border: "1px solid #d1d5db",
                    fontSize: 11, cursor: canAck ? "pointer" : "not-allowed",
                    background: "#fff", minWidth: 130,
                    opacity: canAck ? 1 : 0.5,
                  }}
                >
                  <option value="">Grund wählen…</option>
                  {shiftReasons.map(r => (
                    <option key={r.code} value={r.code}>{r.code}: {r.label}</option>
                  ))}
                </select>
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    if (!canAck) { onError?.("Keine Berechtigung für Schiebungen."); return; }
                    if (!shiftVal) return;
                    try { await onShiftRule?.(caseId, item.rule_id!, shiftVal); }
                    catch (err: any) { onError?.(err?.message ?? String(err)); }
                  }}
                  style={{
                    padding: "5px 12px", fontSize: 11, borderRadius: 6,
                    border: "1px solid #d1d5db",
                    background: canAck && shiftVal ? "#f8fafc" : "#f3f4f6",
                    cursor: canAck && shiftVal ? "pointer" : "not-allowed",
                    opacity: canAck && shiftVal ? 1 : 0.5, fontWeight: 600,
                    color: "#374151",
                  }}
                >
                  ⏭ Nochmal erinnern
                </button>
              </div>

              {/* Spacer */}
              <div style={{ flex: 1 }} />

              {/* ACK: Behoben / Gesehen */}
              <button
                onClick={async (e) => {
                  e.stopPropagation();
                  if (!canAck) { onError?.("Keine Berechtigung für Quittierungen."); return; }
                  try { await onAckRule?.(caseId, item.rule_id!); }
                  catch (err: any) { onError?.(err?.message ?? String(err)); }
                }}
                style={{
                  padding: "5px 16px", fontSize: 12, borderRadius: 6,
                  border: "none",
                  background: canAck ? "#1f2937" : "#9ca3af",
                  color: "#fff",
                  fontWeight: 700,
                  cursor: canAck ? "pointer" : "not-allowed",
                  boxShadow: canAck ? "0 1px 3px rgba(0,0,0,0.15)" : "none",
                }}
              >
                ✓ {ackLabel(item.group)}
              </button>
            </div>
          )}

          {/* Items ohne rule_id: nur Info, kein ACK möglich */}
          {!item.rule_id && isProblem && !item.ack && (
            <div style={{ fontSize: 10, color: "#9ca3af", fontStyle: "italic", marginTop: 4 }}>
              Kein Regelabgleich — wird durch Datenkorrektur aufgelöst.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Helpers ─── */
function fmtTs(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getDate()}.${d.getMonth() + 1}. ${d.getHours()}:${String(d.getMinutes()).padStart(2, "0")}`;
  } catch { return iso; }
}

const btnStyle: React.CSSProperties = {
  padding: "2px 8px", borderRadius: 4, border: "1px solid #d1d5db",
  background: "#fff", fontSize: 10, color: "#6b7280", cursor: "pointer",
};
