import { useEffect, useMemo, useRef, useState } from "react";
import type { CaseSummary, CaseDetail, Severity } from "./types";
import { Toast } from "./Toast";

type ToastState =
  | { caseId: string; message: string; kind: "critical" | "warn" | "info" }
  | null;

type AuthState = {
  stationId: string;
  userId: string;
  rolesCsv: string; // "VIEW_DASHBOARD,ACK_ALERT"
};


type MetaUser = { user_id: string; roles: string[] };

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

export default function App() {
  const [auth, setAuth] = useState<AuthState>(() => loadAuth());
  const [stations, setStations] = useState<string[]>(["A1", "B0", "B2"]);
  const [metaUsers, setMetaUsers] = useState<MetaUser[]>([
    { user_id: "demo", roles: ["VIEW_DASHBOARD", "ACK_ALERT"] },
    { user_id: "pflege1", roles: ["VIEW_DASHBOARD"] },
    { user_id: "arzt1", roles: ["VIEW_DASHBOARD", "ACK_ALERT"] },
    { user_id: "manager1", roles: ["VIEW_DASHBOARD", "ACK_ALERT"] },
  ]);
  const [metaError, setMetaError] = useState<string | null>(null);

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
        setDetail(d);
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

  // Load station/user choices from backend (prototyp) so you don't need to know valid IDs.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const st = await fetch("/api/meta/stations").then(r => r.ok ? r.json() : Promise.reject(new Error("meta/stations")));
        if (alive && Array.isArray(st?.stations) && st.stations.length) {
          setStations(st.stations);
          if (!st.stations.includes(auth.stationId)) {
            updateAuth({ stationId: st.stations[0] });
          }
        }
      } catch (e: any) {
        // keep defaults
      }

      try {
        const us = await fetch("/api/meta/users").then(r => r.ok ? r.json() : Promise.reject(new Error("meta/users")));
        if (alive && Array.isArray(us?.users) && us.users.length) {
          setMetaUsers(us.users);
          const u = us.users.find((x: MetaUser) => x.user_id === auth.userId) ?? us.users[0];
          if (u) {
            updateAuth({ userId: u.user_id, rolesCsv: (u.roles ?? []).join(",") });
          }
        }
      } catch (e: any) {
        if (!alive) return;
        setMetaError("Meta-Endpoints nicht erreichbar (Fallback aktiv).");
      }
    })();

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When user changes, derive roles automatically from meta list (no free-text roles).
  useEffect(() => {
    const u = metaUsers.find((x) => x.user_id === auth.userId);
    if (u) {
      const next = (u.roles ?? []).join(",");
      if (next && next !== auth.rolesCsv) updateAuth({ rolesCsv: next });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.userId, metaUsers]);

  function splitRoles(rolesCsv: string): string[] {
    return rolesCsv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  return (
    <main style={{ padding: "1rem", fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial" }}>
      <style>{`
        :root{ --app-bg:#f6f7fb; --card:#ffffff; --border:#e6e8ef; --text:#0f172a; --muted:#64748b; --shadow:0 6px 20px rgba(15,23,42,.06); }
        body{ background:var(--app-bg); color:var(--text); }
        .wrap{ max-width:1200px; margin:0 auto; }
        .panel{ background:var(--card); border:1px solid var(--border); border-radius:14px; box-shadow:var(--shadow); }
        .gridMain{ display:grid; grid-template-columns: 1.1fr 0.9fr; gap:16px; align-items:start; }
        @media (max-width: 980px){ .gridMain{ grid-template-columns: 1fr; } }
        .toolbar{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
        .search{ padding:10px 12px; border-radius:12px; border:1px solid var(--border); width: min(520px, 100%); background:#fff; }
        .btn{ padding:8px 12px; border-radius:12px; border:1px solid var(--border); background:#fff; cursor:pointer; }
        .btn:disabled{ opacity:.5; cursor:not-allowed; }
      `}</style>
      <div className="wrap">

      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Dashboard – Station {auth.stationId}</h1>
          <div style={{ fontSize: 12, opacity: 0.75 }}>
            User: <code>{auth.userId}</code> · Rollen: <code>{auth.rolesCsv || "—"}</code>
          </div>
        </div>

        <details style={{ border: "1px solid #ddd", borderRadius: 10, padding: "0.6rem 0.9rem", background: "#fff" }}>
          <summary style={{ cursor: "pointer", fontWeight: 600 }}>Kontext (Prototyp)</summary>
          <div style={{ marginTop: 10, display: "grid", gap: 10, minWidth: 320 }}>
            <div style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, opacity: 0.75 }}>Station</span>
              <select
                value={auth.stationId}
                onChange={(e) => updateAuth({ stationId: e.target.value })}
                style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}
              >
                {stations.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, opacity: 0.75 }}>User</span>
              <select
                value={auth.userId}
                onChange={(e) => updateAuth({ userId: e.target.value })}
                style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}
              >
                {metaUsers.map((u) => (
                  <option key={u.user_id} value={u.user_id}>{u.user_id}</option>
                ))}
              </select>
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              <span style={{ fontSize: 12, opacity: 0.75 }}>Rollen</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {splitRoles(auth.rolesCsv).map((r) => (
                  <span key={r} style={{ fontSize: 12, padding: "2px 8px", borderRadius: 999, border: "1px solid #ddd", background: "#fafafa" }}>
                    {r}
                  </span>
                ))}
              </div>
              <div style={{ fontSize: 12, opacity: 0.65 }}>
                Rollen werden aus dem User abgeleitet (kein Freitext). {metaError ? `(${metaError})` : ""}
              </div>
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
                  {detail.alerts.map((a) => (
                    <li key={a.rule_id} style={{ marginBottom: 10 }}>
                      <strong>{a.severity}:</strong> {a.message}
                      <div style={{ fontSize: "0.9em", opacity: 0.9 }}>{a.explanation}</div>
                      {/* Rule-level ack could go here later (ack_scope="rule", scope_id=a.rule_id) */}
                    </li>
                  ))}
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
          </div>
    </main>
  );
}
