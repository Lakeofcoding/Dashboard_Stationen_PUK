import { useEffect, useMemo, useRef, useState } from "react";
import type { CaseSummary, CaseDetail, Severity, Alert } from "./types";
import { Toast } from "./Toast";

type ToastState =
  | { caseId: string; message: string; kind: "critical" | "warn" | "info" }
  | null;

type AuthState = {
  stationId: string;
  userId: string;
  rolesCsv: string; // "VIEW_DASHBOARD,ACK_ALERT"
};

const LS_KEYS = {
  stationId: "dashboard.stationId",
  userId: "dashboard.userId",
  rolesCsv: "dashboard.rolesCsv",
};

function severityColor(severity: Severity): string {
  switch (severity) {
    case "CRITICAL":
      return "#ffe5e5";
    case "WARN":
      return "#fff6d6";
    default:
      return "#e8f5e9";
  }
}

function loadAuth(): AuthState {
  return {
    stationId: localStorage.getItem(LS_KEYS.stationId) ?? "ST01",
    userId: localStorage.getItem(LS_KEYS.userId) ?? "demo",
    rolesCsv: localStorage.getItem(LS_KEYS.rolesCsv) ?? "VIEW_DASHBOARD,ACK_ALERT",
  };
}

function saveAuth(a: AuthState) {
  localStorage.setItem(LS_KEYS.stationId, a.stationId);
  localStorage.setItem(LS_KEYS.userId, a.userId);
  localStorage.setItem(LS_KEYS.rolesCsv, a.rolesCsv);
}

function parseRoles(csv: string): Set<string> {
  return new Set(
    csv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );
}

function authHeaders(auth: AuthState): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Station-Id": auth.stationId,
    "X-User-Id": auth.userId,
    "X-Roles": auth.rolesCsv,
  };
}

async function apiJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

async function fetchCases(auth: AuthState): Promise<CaseSummary[]> {
  return apiJson<CaseSummary[]>("/api/cases", {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function fetchCaseDetail(caseId: string, auth: AuthState): Promise<CaseDetail> {
  return apiJson<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`, {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function ackCase(caseId: string, auth: AuthState): Promise<{ acked_at: string }> {
  return apiJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, ack_scope: "case", scope_id: "*" }),
  });
}

async function ackRule(caseId: string, ruleId: string, auth: AuthState): Promise<{ acked_at: string }> {
  return apiJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, ack_scope: "rule", scope_id: ruleId }),
  });
}

export default function App() {
  const [auth, setAuth] = useState<AuthState>(() => loadAuth());
  const roles = useMemo(() => parseRoles(auth.rolesCsv), [auth.rolesCsv]);
  const canAck = roles.has("ACK_ALERT");

  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [toast, setToast] = useState<ToastState>(null);

  // Dedup for critical toasts across refresh cycles (per session)
  const shownCriticalRef = useRef<Record<string, true>>({});

  // Polling: prototype-friendly. Keep interval moderate.
  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const data = await fetchCases(auth);
        if (!alive) return;
        setCases(data);
        setError(null);

        // Only show CRITICAL toast if:
        // - there is currently no toast open
        // - case is CRITICAL and not acked
        // - toast for that case wasn't shown already
        if (!toast) {
          const firstCritical = data.find(
            (c) => c.severity === "CRITICAL" && !c.acked_at && !shownCriticalRef.current[c.case_id]
          );
          if (firstCritical) {
            setToast({
              kind: "critical",
              caseId: firstCritical.case_id,
              message: `${firstCritical.case_id}: ${firstCritical.top_alert ?? "Kritischer Status"}`,
            });
            shownCriticalRef.current[firstCritical.case_id] = true;
          }
        }
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message ?? String(e));
      }
    };

    // initial + interval
    load();
    const id = window.setInterval(load, 10_000);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
    // auth changes should restart polling
  }, [auth, toast]);

  // Load detail when selection changes OR auth changes (station context changes)
  useEffect(() => {
    if (!selectedCaseId) {
      setDetail(null);
      setDetailError(null);
      return;
    }

    setDetailLoading(true);
    fetchCaseDetail(selectedCaseId, auth)
      .then((d) => {
        // Backend may omit rule_acks in early versions; normalize for UI.
        const normalized = { ...d, rule_acks: d.rule_acks ?? {} };
        setDetail(normalized);
        setDetailError(null);
      })
      .catch((err) => setDetailError(err?.message ?? String(err)))
      .finally(() => setDetailLoading(false));
  }, [selectedCaseId, auth]);

  // Keep detail acked_at in sync with list after polling refresh
  useEffect(() => {
    if (!detail || !selectedCaseId) return;
    const fromList = cases.find((c) => c.case_id === selectedCaseId);
    if (!fromList) return;
    if (fromList.acked_at !== detail.acked_at) {
      setDetail({ ...detail, acked_at: fromList.acked_at });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases, selectedCaseId]);

  function updateAuth(patch: Partial<AuthState>) {
    const next = { ...auth, ...patch };
    setAuth(next);
    saveAuth(next);
  }

  return (
    <main style={{ padding: "1rem", fontFamily: "sans-serif" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Dashboard – Station {auth.stationId}</h1>
          <div style={{ fontSize: 12, opacity: 0.75 }}>
            User: <code>{auth.userId}</code> · Rollen: <code>{auth.rolesCsv || "—"}</code>
          </div>
        </div>

        <details style={{ border: "1px solid #ddd", borderRadius: 6, padding: "0.5rem 0.75rem" }}>
          <summary style={{ cursor: "pointer" }}>Kontext (Prototyp)</summary>
          <div style={{ marginTop: 8, display: "grid", gap: 8, minWidth: 320 }}>
            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12, opacity: 0.8 }}>Station-ID</span>
              <input
                value={auth.stationId}
                onChange={(e) => updateAuth({ stationId: e.target.value.trim() || "ST01" })}
                style={{ padding: 6, borderRadius: 6, border: "1px solid #ccc" }}
                placeholder="ST01"
              />
            </label>

            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12, opacity: 0.8 }}>User-ID</span>
              <input
                value={auth.userId}
                onChange={(e) => updateAuth({ userId: e.target.value.trim() || "demo" })}
                style={{ padding: 6, borderRadius: 6, border: "1px solid #ccc" }}
                placeholder="demo"
              />
            </label>

            <label style={{ display: "grid", gap: 4 }}>
              <span style={{ fontSize: 12, opacity: 0.8 }}>Rollen (CSV)</span>
              <input
                value={auth.rolesCsv}
                onChange={(e) => updateAuth({ rolesCsv: e.target.value })}
                style={{ padding: 6, borderRadius: 6, border: "1px solid #ccc" }}
                placeholder="VIEW_DASHBOARD,ACK_ALERT"
              />
            </label>

            <div style={{ fontSize: 12, opacity: 0.8 }}>
              Ack möglich: <strong>{canAck ? "Ja" : "Nein"}</strong> (Role <code>ACK_ALERT</code>)
            </div>
          </div>
        </details>
      </div>

      {error && <p style={{ color: "red" }}>Fehler: {error}</p>}

      <div
        style={{
          marginTop: 12,
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: "1rem",
          alignItems: "start",
        }}
      >
        {/* Left: Cards */}
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {cases.map((c) => (
            <button
              key={c.case_id}
              onClick={() => setSelectedCaseId(c.case_id)}
              style={{
                textAlign: "left",
                padding: "0.75rem 1rem",
                borderRadius: 6,
                background: severityColor(c.severity),
                border: selectedCaseId === c.case_id ? "2px solid #333" : "1px solid #ddd",
                cursor: "pointer",
                opacity: c.acked_at ? 0.7 : 1,
              }}
              title={c.acked_at ? `Quittiert: ${c.acked_at}` : "Nicht quittiert"}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ fontWeight: 700 }}>{c.case_id}</div>
                {c.acked_at ? (
                  <span style={{ fontSize: 12, opacity: 0.85 }}>✓ quittiert</span>
                ) : c.severity === "CRITICAL" ? (
                  <span style={{ fontSize: 12, opacity: 0.85 }}>‼ kritisch</span>
                ) : null}
              </div>

              <div>Status: {c.severity}</div>
              {c.top_alert && <div style={{ marginTop: 4 }}>⚠ {c.top_alert}</div>}
            </button>
          ))}

          {cases.length === 0 && !error && <p style={{ opacity: 0.8 }}>Keine Fälle für diese Station.</p>}
        </div>

        {/* Right: Detail Panel */}
        <aside
          style={{
            border: "1px solid #ddd",
            borderRadius: 6,
            padding: "0.75rem 1rem",
            background: "#fff",
            minHeight: 200,
          }}
        >
          {!selectedCaseId && <p>Fall auswählen, um Details zu sehen.</p>}

          {selectedCaseId && detailLoading && <p>Lade Details…</p>}

          {selectedCaseId && detailError && <p style={{ color: "red" }}>Fehler: {detailError}</p>}

          {detail && !detailLoading && !detailError && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <h2 style={{ margin: 0, fontSize: "1.1rem" }}>{detail.case_id}</h2>
                <button onClick={() => setSelectedCaseId(null)} aria-label="Close details">
                  ✕
                </button>
              </div>

              <p style={{ marginTop: 8 }}>
                <strong>Quittiert:</strong> {detail.acked_at ? `Ja (${detail.acked_at})` : "Nein"}
              </p>

              {!detail.acked_at && (
                <button
                  disabled={!canAck}
                  onClick={async () => {
                    if (!canAck) return;
                    try {
                      const res = await ackCase(detail.case_id, auth);

                      // optimistic update: update detail and list
                      setDetail({ ...detail, acked_at: res.acked_at });
                      setCases((prev) =>
                        prev.map((c) => (c.case_id === detail.case_id ? { ...c, acked_at: res.acked_at } : c))
                      );

                      // clear toast if it refers to this case
                      setToast((t) => (t && t.caseId === detail.case_id ? null : t));
                    } catch (e: any) {
                      setError(e?.message ?? String(e));
                    }
                  }}
                  style={{
                    marginTop: 8,
                    padding: "8px 12px",
                    borderRadius: 6,
                    border: "1px solid #333",
                    background: canAck ? "#333" : "#999",
                    color: "white",
                    fontWeight: 600,
                    cursor: canAck ? "pointer" : "not-allowed",
                  }}
                  title={canAck ? "Fall quittieren" : "Keine Berechtigung (ACK_ALERT fehlt)"}
                >
                  Fall quittieren
                </button>
              )}

              <p style={{ marginTop: 12 }}>
                <strong>Station:</strong> {detail.station_id}
                <br />
                <strong>Eintritt:</strong> {detail.admission_date}
                <br />
                <strong>HONOS:</strong> {detail.honos ?? "—"}
                <br />
                <strong>BSCL:</strong> {detail.bscl ?? "—"}
                <br />
                <strong>BFS vollständig:</strong> {detail.bfs_complete ? "Ja" : "Nein"}
              </p>

              <h3 style={{ marginBottom: 6, fontSize: "1rem" }}>Alerts</h3>
              {detail.alerts.length === 0 ? (
                <p>Keine Alerts.</p>
              ) : (
                <ul style={{ paddingLeft: 18, marginTop: 0 }}>
                  {detail.alerts.map((a: Alert) => {
                    const ruleAckedAt = detail.rule_acks?.[a.rule_id];
                    return (
                      <li key={a.rule_id} style={{ marginBottom: 10 }}>
                        <strong>{a.severity}:</strong> {a.message}
                        <div style={{ fontSize: "0.9em", opacity: 0.9 }}>{a.explanation}</div>

                        <div style={{ marginTop: 6, display: "flex", gap: 10, alignItems: "center" }}>
                          <span style={{ fontSize: 12, opacity: 0.8 }}>
                            {ruleAckedAt ? `✓ Regel quittiert (${ruleAckedAt})` : "Regel nicht quittiert"}
                          </span>

                          {!ruleAckedAt && (
                            <button
                              disabled={!canAck}
                              onClick={async () => {
                                if (!canAck) return;
                                try {
                                  const res = await ackRule(detail.case_id, a.rule_id, auth);
                                  setDetail({
                                    ...detail,
                                    rule_acks: { ...(detail.rule_acks ?? {}), [a.rule_id]: res.acked_at },
                                  });
                                } catch (e: any) {
                                  setError(e?.message ?? String(e));
                                }
                              }}
                              style={{
                                padding: "6px 10px",
                                borderRadius: 6,
                                border: "1px solid #333",
                                background: canAck ? "#333" : "#999",
                                color: "white",
                                fontWeight: 600,
                                cursor: canAck ? "pointer" : "not-allowed",
                              }}
                              title={canAck ? "Diese Regel quittieren" : "Keine Berechtigung (ACK_ALERT fehlt)"}
                            >
                              Regel quittieren
                            </button>
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </aside>
      </div>

      {toast && (
        <Toast
          kind={toast.kind}
          message={toast.message}
          actionLabel={canAck ? "Quittieren" : undefined}
          onAction={
            canAck
              ? async () => {
                  try {
                    await ackCase(toast.caseId, auth);
                    setToast(null);
                    // refresh list to reflect ack
                    const data = await fetchCases(auth);
                    setCases(data);
                  } catch (e: any) {
                    setError(e?.message ?? String(e));
                  }
                }
              : undefined
          }
          onClose={() => setToast(null)}
        />
      )}
    </main>
  );
}
