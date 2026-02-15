/**
 * Datei: frontend/src/App.tsx
 *
 * Zweck:
 * - Hauptkomponente des PUK Dashboard
 * - Case-Übersicht, Detail-Ansicht, Alerts
 *
 * Änderungen:
 * - "Schieben" → "Nochmal erinnern"
 * - "Quittieren" bei completeness → "Behoben"
 * - "Quittieren" bei medical → "Gesehen"
 * - Farbcodierung: OK=#e8f5e9, WARN=#fff6d6, CRITICAL=#ffe5e5
 * - Austritt-Anzeige: discharge_date oder "Offener Fall"
 * - Fall-Quittierung entfernt (nur Alert-Quittierung)
 * - Shift-Gründe dynamisch aus API
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { CaseSummary, CaseDetail, Severity, DayState } from "./types";
import { Toast } from "./Toast";
import { AdminPanel } from "./AdminPanel";

type ToastState =
  | { caseId: string; message: string; kind: "critical" | "warn" | "info" }
  | null;

type AuthState = {
  stationId: string;
  userId: string;
};

type MetaUser = { user_id: string; roles: string[] };

type MetaMe = {
  user_id: string;
  station_id: string;
  roles: string[];
  permissions: string[];
  break_glass: boolean;
};

type ShiftReason = {
  id: number;
  code: string;
  label: string;
  description: string | null;
};

const LS_KEYS = {
  stationId: "dashboard.stationId",
  userId: "dashboard.userId",
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

function severityBorderColor(severity: Severity): string {
  switch (severity) {
    case "CRITICAL":
      return "#f87171";
    case "WARN":
      return "#fbbf24";
    default:
      return "#86efac";
  }
}

/** Returns the appropriate label for the "acknowledge" button based on alert category */
function ackLabel(category: string): string {
  if (category === "completeness") return "Behoben";
  return "Gesehen";
}

function loadAuth(): AuthState {
  return {
    stationId: localStorage.getItem(LS_KEYS.stationId) ?? "A1",
    userId: localStorage.getItem(LS_KEYS.userId) ?? "demo",
  };
}

function saveAuth(a: AuthState) {
  localStorage.setItem(LS_KEYS.stationId, a.stationId);
  localStorage.setItem(LS_KEYS.userId, a.userId);
}

function authHeaders(auth: AuthState): HeadersInit {
  return {
    "Content-Type": "application/json",
    "X-Station-Id": auth.stationId,
    "X-User-Id": auth.userId,
  };
}

function isAdminPath(pathname: string): boolean {
  return pathname.startsWith("/api/admin/");
}

function headerLookup(h: HeadersInit | undefined, key: string): string | undefined {
  if (!h) return undefined;
  if (h instanceof Headers) return h.get(key) ?? undefined;
  if (Array.isArray(h)) {
    const found = h.find(([k]) => k.toLowerCase() === key.toLowerCase());
    return found?.[1];
  }
  const obj = h as Record<string, string>;
  const direct = obj[key];
  if (direct) return direct;
  const lowerKey = key.toLowerCase();
  for (const k of Object.keys(obj)) {
    if (k.toLowerCase() === lowerKey) return obj[k];
  }
  return undefined;
}

function withCtx(path: string, init: RequestInit): string {
  if (!path.startsWith("/api/")) return path;
  const url = new URL(path, window.location.origin);
  if (isAdminPath(url.pathname)) return url.pathname + url.search;
  if (url.searchParams.has("ctx")) return url.pathname + url.search;
  const h = init.headers;
  const ctx =
    headerLookup(h, "X-Scope-Ctx") ||
    headerLookup(h, "X-Station-Id") ||
    localStorage.getItem(LS_KEYS.stationId) ||
    "global";
  url.searchParams.set("ctx", ctx);
  return url.pathname + "?" + url.searchParams.toString();
}

async function apiJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(withCtx(path, init), init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

type ViewMode = "all" | "completeness" | "medical" | "admin";

async function fetchCases(auth: AuthState, view: ViewMode): Promise<CaseSummary[]> {
  // Backend only accepts "all", "completeness", "medical"; admin is a UI-only mode
  const apiView = (view === "admin") ? "all" : view;
  const qs = new URLSearchParams({ view: apiView }).toString();
  return apiJson<CaseSummary[]>(`/api/cases?${qs}`, {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function fetchCaseDetail(caseId: string, auth: AuthState, view: ViewMode): Promise<CaseDetail> {
  const apiView = (view === "admin") ? "all" : view;
  const qs = new URLSearchParams({ view: apiView }).toString();
  return apiJson<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}?${qs}`, {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function ackRule(caseId: string, ruleId: string, auth: AuthState): Promise<{ acked_at: string }> {
  return apiJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, ack_scope: "rule", scope_id: ruleId }),
  });
}

async function shiftRule(
  caseId: string,
  ruleId: string,
  shift: string,
  auth: AuthState
): Promise<{ acked_at: string }> {
  return apiJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({
      case_id: caseId,
      ack_scope: "rule",
      scope_id: ruleId,
      action: "SHIFT",
      shift_code: shift,
    }),
  });
}

async function fetchDayState(auth: AuthState): Promise<DayState> {
  return apiJson<DayState>("/api/day_state", {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function resetToday(auth: AuthState): Promise<DayState> {
  return apiJson<DayState>("/api/reset_today", {
    method: "POST",
    headers: authHeaders(auth),
  });
}

async function fetchShiftReasons(auth: AuthState): Promise<ShiftReason[]> {
  try {
    const data = await apiJson<{ reasons: ShiftReason[] }>("/api/shift_reasons", {
      method: "GET",
      headers: authHeaders(auth),
    });
    return data.reasons;
  } catch {
    return [
      { id: 1, code: "a", label: "Noch in Bearbeitung", description: null },
      { id: 2, code: "b", label: "Warte auf Rückmeldung", description: null },
      { id: 3, code: "c", label: "Nicht relevant", description: null },
    ];
  }
}

function ClinicLogo({ title = "Klinik" }: { title?: string }) {
  return (
    <svg width="180" height="28" viewBox="0 0 180 28" role="img" aria-label={title} style={{ display: "block" }}>
      <title>{title}</title>
      <rect x="0.5" y="0.5" width="179" height="27" rx="8" fill="#ffffff" stroke="#cbd5e1" />
      <rect x="10" y="9" width="18" height="12" rx="2" fill="#e2e8f0" stroke="#94a3b8" />
      <rect x="30" y="6" width="22" height="15" rx="2" fill="#e2e8f0" stroke="#94a3b8" />
      <rect x="54" y="9" width="18" height="12" rx="2" fill="#e2e8f0" stroke="#94a3b8" />
      <rect x="14" y="12" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="20" y="12" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="34" y="10" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="40" y="10" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="46" y="10" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="34" y="16" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="40" y="16" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="46" y="16" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="58" y="12" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="64" y="12" width="4" height="4" fill="#ffffff" stroke="#94a3b8" />
      <rect x="41" y="18" width="4" height="3" fill="#ffffff" stroke="#94a3b8" />
      <rect x="82" y="9" width="10" height="10" rx="2" fill="#fff1f2" stroke="#fb7185" />
      <rect x="86.2" y="10.7" width="1.6" height="6.6" fill="#e11d48" />
      <rect x="83.7" y="13.2" width="6.6" height="1.6" fill="#e11d48" />
      <text x="100" y="18" fontSize="12" fontFamily="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial" fill="#0f172a">
        Klinik
      </text>
    </svg>
  );
}

export default function App() {
  const [auth, setAuth] = useState<AuthState>(() => loadAuth());
  const [me, setMe] = useState<MetaMe | null>(null);

  const [stations, setStations] = useState<string[]>(["A1", "B0", "B2"]);
  const [metaUsers, setMetaUsers] = useState<MetaUser[]>([
    { user_id: "demo", roles: ["admin"] },
  ]);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [shiftReasons, setShiftReasons] = useState<ShiftReason[]>([]);

  const permissions = useMemo(() => new Set(me?.permissions ?? []), [me]);
  const canAck = permissions.has("ack:write");
  const canReset = permissions.has("reset:today");
  const canAdmin =
    permissions.has("admin:read") || permissions.has("admin:write") || permissions.has("audit:read");

  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [dayState, setDayState] = useState<DayState | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [shiftByAlert, setShiftByAlert] = useState<Record<string, string>>({});
  const shownCriticalRef = useRef<Record<string, true>>({});

  const setShift = (caseId: string, ruleId: string, value: string) => {
    setShiftByAlert((prev) => ({ ...prev, [`${caseId}::${ruleId}`]: value }));
  };

  function updateAuth(patch: Partial<AuthState>) {
    const next = { ...auth, ...patch };
    setAuth(next);
    saveAuth(next);
  }

  // Reset on context change
  useEffect(() => {
    setSelectedCaseId(null);
    setDetail(null);
    setDetailError(null);
    setDetailLoading(false);
    setShiftByAlert({});
    setToast(null);
    shownCriticalRef.current = {};
  }, [auth.stationId, auth.userId]);

  // Load me
  useEffect(() => {
    (async () => {
      try {
        const data = await apiJson<MetaMe>("/api/meta/me", { method: "GET", headers: authHeaders(auth) });
        setMe(data);
      } catch {
        setMe(null);
      }
    })();
  }, [auth.stationId, auth.userId]);

  // Load shift reasons
  useEffect(() => {
    fetchShiftReasons(auth).then(setShiftReasons);
  }, [auth.stationId, auth.userId]);

  // Load cases + day state
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [data, ds] = await Promise.all([fetchCases(auth, viewMode), fetchDayState(auth)]);
        if (!alive) return;
        setCases(data);
        setDayState(ds);
        setError(null);

        if (!toast) {
          const firstCritical = data.find(
            (c) =>
              (c.critical_count ?? (c.severity === "CRITICAL" ? 1 : 0)) > 0 &&
              !shownCriticalRef.current[c.case_id]
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
    load();
    const id = window.setInterval(load, 10_000);
    return () => { alive = false; window.clearInterval(id); };
  }, [auth, toast, viewMode]);

  // Load detail
  useEffect(() => {
    if (!selectedCaseId) { setDetail(null); setDetailError(null); return; }
    setDetailLoading(true);
    fetchCaseDetail(selectedCaseId, auth, viewMode)
      .then((d) => { setDetail(d); setDetailError(null); })
      .catch((err) => {
        const msg = err?.message ?? String(err);
        if (String(msg).includes("404")) { setSelectedCaseId(null); setDetail(null); return; }
        setDetailError(msg);
      })
      .finally(() => setDetailLoading(false));
  }, [selectedCaseId, auth, viewMode]);

  // Sync detail with list
  useEffect(() => {
    if (!detail || !selectedCaseId) return;
    const fromList = cases.find((c) => c.case_id === selectedCaseId);
    if (!fromList) return;
    if (fromList.acked_at !== detail.acked_at) {
      setDetail({ ...detail, acked_at: fromList.acked_at });
    }
  }, [cases, selectedCaseId]);

  // Meta stations/users
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const st = await apiJson<{ stations: string[] }>("/api/meta/stations", { method: "GET", headers: authHeaders(auth) });
        if (alive && Array.isArray(st?.stations) && st.stations.length) {
          setStations(st.stations);
          if (!st.stations.includes(auth.stationId)) updateAuth({ stationId: st.stations[0] });
        }
      } catch { /* keep defaults */ }
      try {
        const us = await apiJson<{ users: MetaUser[] }>("/api/meta/users", { method: "GET", headers: authHeaders(auth) });
        if (alive && Array.isArray(us?.users) && us.users.length) {
          setMetaUsers(us.users);
          const u = us.users.find((x: MetaUser) => x.user_id === auth.userId) ?? us.users[0];
          if (u) updateAuth({ userId: u.user_id });
        }
      } catch (e: any) {
        if (!alive) return;
        setMetaError("Meta-Endpoints nicht erreichbar (Fallback aktiv).");
      }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh", width: "100vw", overflow: "hidden", fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial", backgroundColor: "#f4f7f6" }}>
      {/* HEADER */}
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "stretch", padding: "0.8rem 1.5rem", backgroundColor: "#fff", borderBottom: "1px solid #d1d9e0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)", zIndex: 100, gap: 16 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0 }}>
            <h1 style={{ margin: 0, fontSize: "1.25rem", color: "#1a1a1a", lineHeight: 1.1 }}>Stations-Dashboard</h1>
            <div style={{ marginLeft: 8, flexShrink: 0 }}><ClinicLogo title="Klinik-Logo (Dummy)" /></div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, minWidth: 0, flexWrap: "wrap" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>Station</span>
              <select value={auth.stationId} onChange={(e) => updateAuth({ stationId: e.target.value })} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc", background: "#fff", cursor: "pointer" }}>
                {stations.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 12, color: "#666", fontWeight: 700 }}>User</span>
              <select value={auth.userId} onChange={(e) => updateAuth({ userId: e.target.value })} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc", background: "#fff", cursor: "pointer" }}>
                {metaUsers.map((u) => <option key={u.user_id} value={u.user_id}>{u.user_id} ({(u.roles ?? []).join(",") || "—"})</option>)}
              </select>
            </label>
            {dayState ? <span style={{ color: "#666", fontSize: "0.9rem", whiteSpace: "nowrap" }}>· Tag: {dayState.business_date} · Vers: {dayState.version}</span> : null}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", justifyContent: "flex-end" }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "#666" }}>Sicht</span>
            <select value={viewMode} onChange={(e) => setViewMode(e.target.value as ViewMode)} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc", background: "#fff", cursor: "pointer" }}>
              <option value="all">Alle</option>
              <option value="completeness">Vollständigkeit</option>
              <option value="medical">Medizinisch</option>
              {canAdmin ? <option value="admin">Admin</option> : null}
            </select>
          </label>

          <button
            onClick={async () => {
              if (!canReset) return;
              if (!window.confirm(`Achtung:\n\nDadurch werden alle heutigen Quittierungen und Erinnerungen für Station ${auth.stationId} zurückgesetzt.\n\nAlle Meldungen erscheinen wieder als offen.\n\nFortfahren?`)) return;
              try {
                const ds = await resetToday(auth);
                setDayState(ds);
                const data = await fetchCases(auth, viewMode);
                setCases(data);
                setSelectedCaseId(null); setDetail(null); setDetailError(null); setShiftByAlert({});
              } catch (e: any) { setError(e?.message ?? String(e)); }
            }}
            disabled={!canReset}
            style={{ padding: "6px 12px", cursor: canReset ? "pointer" : "not-allowed", borderRadius: 10, border: "1px solid #ccc", background: canReset ? "#fff" : "#f0f0f0", opacity: canReset ? 1 : 0.6 }}
            title={canReset ? "Reset: alle heutigen Quittierungen verwerfen" : "Keine Berechtigung"}
          >
            Reset (heute)
          </button>

          <div style={{ fontSize: "0.85rem", textAlign: "right", lineHeight: 1.2 }}>
            <div style={{ fontWeight: 700 }}>{me?.user_id || auth.userId}</div>
            <div style={{ color: "#666" }}>Rollen: {(me?.roles ?? []).join(", ") || "—"}</div>
          </div>

          <button onClick={() => setIsAdminOpen(true)} disabled={!canAdmin} style={{ padding: "6px 12px", cursor: canAdmin ? "pointer" : "not-allowed", borderRadius: 10, border: "1px solid #ccc", background: canAdmin ? "#f0f0f0" : "#f6f6f6", opacity: canAdmin ? 1 : 0.6 }} title={canAdmin ? "Admin öffnen" : "Keine Admin-Rechte"}>
            ⚙ Admin
          </button>
        </div>
      </header>

      {metaError ? <div style={{ padding: "10px 16px", color: "#666", background: "#fff", borderBottom: "1px solid #eee" }}>{metaError}</div> : null}
      {error && <div style={{ padding: "10px 16px", color: "#b42318", background: "#fff", borderBottom: "1px solid #eee" }}>Fehler: {error}</div>}

      {/* MAIN: split */}
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* LEFT: case list */}
        <section style={{ flex: "0 0 380px", borderRight: "1px solid #d1d9e0", overflowY: "auto", backgroundColor: "#fff" }}>
          {cases.length === 0 ? (
            <div style={{ padding: 20, color: "#999" }}>Keine Fälle für diese Station.</div>
          ) : (
            cases.map((c) => {
              const isSelected = selectedCaseId === c.case_id;
              const critical = (c.critical_count ?? (c.severity === "CRITICAL" ? 1 : 0)) > 0;

              return (
                <div
                  key={c.case_id}
                  onClick={() => setSelectedCaseId(c.case_id)}
                  style={{
                    padding: "14px 14px",
                    borderBottom: "1px solid #eee",
                    cursor: "pointer",
                    backgroundColor: isSelected ? "#eef6ff" : severityColor(c.severity),
                    borderLeft: isSelected
                      ? "4px solid #007bff"
                      : `4px solid ${severityBorderColor(c.severity)}`,
                    transition: "background 0.2s",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
                    <div style={{ fontWeight: 700, overflowWrap: "anywhere" }}>{c.case_id}</div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      {critical ? (
                        <span style={{ fontSize: 12, background: "#ff4d4f", color: "white", padding: "2px 8px", borderRadius: 999, whiteSpace: "nowrap" }}>
                          ‼ {c.critical_count ?? 1}
                        </span>
                      ) : null}
                      {!!(c.warn_count && c.warn_count > 0) ? (
                        <span style={{ fontSize: 12, color: "#333", whiteSpace: "nowrap" }}>⚠ {c.warn_count}</span>
                      ) : null}
                    </div>
                  </div>

                  <div style={{ fontSize: "0.85rem", color: "#666", marginTop: 4 }}>
                    Eintritt: {c.admission_date}
                  </div>
                  <div style={{ fontSize: "0.85rem", color: c.discharge_date ? "#444" : "#2563eb", marginTop: 2, fontWeight: c.discharge_date ? 400 : 600 }}>
                    {c.discharge_date ? `Austritt: ${c.discharge_date}` : "Offener Fall"}
                  </div>
                  {c.top_alert ? (
                    <div style={{ fontSize: "0.85rem", color: "#444", marginTop: 6 }}>⚠ {c.top_alert}</div>
                  ) : null}
                </div>
              );
            })
          )}
        </section>

        {/* RIGHT: details */}
        <aside style={{ flex: 1, overflowY: "auto", padding: "1.5rem 1.75rem", position: "relative" }}>
          {detailLoading && <div style={{ position: "absolute", top: 16, right: 16, color: "#666" }}>Lädt…</div>}

          {!selectedCaseId ? (
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", color: "#999" }}>
              Wählen Sie einen Fall aus der Liste aus, um Details anzuzeigen.
            </div>
          ) : detailError ? (
            <div style={{ color: "#b42318" }}>Fehler: {detailError}</div>
          ) : detail ? (
            <div style={{ maxWidth: 980, margin: "0 auto" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: "1.25rem" }}>
                <div style={{ minWidth: 0 }}>
                  <h2 style={{ margin: 0 }}>Fall: {detail.case_id}</h2>
                  <p style={{ color: "#666", marginTop: 6 }}>Station: {detail.station_id}</p>
                </div>
                {!!(detail as any).break_glass_active ? (
                  <div style={{ background: "#fff2f0", border: "1px solid #ffccc7", padding: 10, borderRadius: 10, color: "#ff4d4f", fontWeight: 800, whiteSpace: "nowrap" }}>
                    ⚠️ NOTFALLZUGRIFF AKTIV
                  </div>
                ) : null}
              </div>

              {/* Info Cards */}
              <div style={{ marginBottom: 18, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                <div style={{ padding: 12, borderRadius: 12, background: "#fff", border: "1px solid #eee" }}>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>Fall</div>
                  <div><strong>Station:</strong> {detail.station_id}</div>
                  <div><strong>Eintritt:</strong> {(detail as any).admission_date ?? "—"}</div>
                  <div style={{ color: detail.discharge_date ? "#333" : "#2563eb", fontWeight: detail.discharge_date ? 400 : 600 }}>
                    <strong>Austritt:</strong> {detail.discharge_date ?? "Offener Fall"}
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 12, background: "#fff", border: "1px solid #eee" }}>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>Scores</div>
                  <div><strong>HONOS:</strong> {(detail as any).honos ?? "—"}</div>
                  <div><strong>BSCL:</strong> {(detail as any).bscl ?? "—"}</div>
                </div>
                <div style={{ padding: 12, borderRadius: 12, background: "#fff", border: "1px solid #eee" }}>
                  <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>Vollständigkeit</div>
                  <div><strong>BFS vollständig:</strong> {(detail as any).bfs_complete ? "Ja" : "Nein"}</div>
                  <div><strong>Status:</strong> {detail.severity === "OK" ? "✓ Alle Daten erfasst" : detail.severity}</div>
                </div>
              </div>

              <h3 style={{ margin: "0 0 10px 0" }}>Alerts</h3>

              {detail.alerts.length === 0 ? (
                <div style={{ color: "#666", padding: 16, background: "#e8f5e9", borderRadius: 12 }}>
                  ✓ Keine offenen Alerts.
                </div>
              ) : (
                <div style={{ display: "grid", gap: 12 }}>
                  {detail.alerts.map((a) => {
                    const key = `${detail.case_id}::${a.rule_id}`;
                    const shiftVal = shiftByAlert[key] ?? "";

                    return (
                      <div
                        key={a.rule_id}
                        style={{
                          padding: 14,
                          borderRadius: 12,
                          backgroundColor: severityColor(a.severity),
                          border: `1px solid ${severityBorderColor(a.severity)}40`,
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          gap: 14,
                        }}
                      >
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 800, marginBottom: 6, overflowWrap: "anywhere" }}>
                            {(a as any).message ?? a.rule_id}
                          </div>
                          {(a as any).explanation ? (
                            <div style={{ fontSize: "0.85rem", color: "#333", marginTop: 4, overflowWrap: "anywhere" }}>
                              {(a as any).explanation}
                            </div>
                          ) : null}
                          <div style={{ fontSize: "0.75rem", color: "#888", marginTop: 4 }}>
                            {a.category === "completeness" ? "📋 Vollständigkeit" : "🏥 Medizinisch"} · {a.severity}
                          </div>
                        </div>

                        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
                          {/* Shift ("Nochmal erinnern") */}
                          <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: 12, color: "#333" }}>Erinnern</span>
                            <select
                              disabled={!canAck}
                              value={shiftVal}
                              onChange={(e) => setShift(detail.case_id, a.rule_id, e.target.value)}
                              style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #333", background: canAck ? "#fff" : "#eee", cursor: canAck ? "pointer" : "not-allowed", maxWidth: 180 }}
                              title="Grund für das Erinnern wählen"
                            >
                              <option value="">–</option>
                              {shiftReasons.map((r) => (
                                <option key={r.code} value={r.code} title={r.description ?? ""}>
                                  {r.code}: {r.label}
                                </option>
                              ))}
                            </select>
                          </label>

                          <button
                            disabled={!canAck || !shiftVal}
                            onClick={async () => {
                              if (!canAck || !shiftVal) return;
                              try {
                                await shiftRule(detail.case_id, a.rule_id, shiftVal, auth);
                                setShift(detail.case_id, a.rule_id, "");
                                const [newList, newDetail] = await Promise.all([fetchCases(auth, viewMode), fetchCaseDetail(detail.case_id, auth, viewMode)]);
                                setCases(newList); setDetail(newDetail);
                              } catch (e: any) { setError(e?.message ?? String(e)); }
                            }}
                            style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #333", background: "#fff", cursor: canAck && shiftVal ? "pointer" : "not-allowed", opacity: canAck && shiftVal ? 1 : 0.6 }}
                            title={canAck ? "Nochmal erinnern" : "Keine Berechtigung"}
                          >
                            Nochmal erinnern
                          </button>

                          {/* Ack: "Behoben" or "Gesehen" */}
                          <button
                            disabled={!canAck}
                            onClick={async () => {
                              if (!canAck) return;
                              try {
                                await ackRule(detail.case_id, a.rule_id, auth);
                                const [newList, newDetail] = await Promise.all([fetchCases(auth, viewMode), fetchCaseDetail(detail.case_id, auth, viewMode)]);
                                setCases(newList); setDetail(newDetail);
                                setToast((t) => {
                                  if (!t || t.caseId !== detail.case_id) return t;
                                  const updated = newList.find((x) => x.case_id === detail.case_id);
                                  if (!updated || (updated.critical_count ?? 0) === 0) return null;
                                  return t;
                                });
                              } catch (e: any) { setError(e?.message ?? String(e)); }
                            }}
                            style={{
                              padding: "8px 14px",
                              borderRadius: 10,
                              border: "1px solid #333",
                              background: canAck ? "#333" : "#999",
                              color: "white",
                              fontWeight: 700,
                              cursor: canAck ? "pointer" : "not-allowed",
                              opacity: canAck ? 1 : 0.6,
                            }}
                            title={canAck
                              ? (a.category === "completeness" ? "Als behoben markieren" : "Als gesehen markieren")
                              : "Keine Berechtigung"}
                          >
                            {ackLabel(a.category)}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ) : null}
        </aside>
      </div>

      {/* ADMIN MODAL */}
      {isAdminOpen && (
        <div role="dialog" aria-modal="true" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.35)", display: "flex", alignItems: "center", justifyContent: "center", padding: 18, zIndex: 1000 }} onClick={() => setIsAdminOpen(false)}>
          <div style={{ width: "min(1100px, 96vw)", maxHeight: "92vh", overflow: "auto", background: "#fff", borderRadius: 14, border: "1px solid #ddd", boxShadow: "0 10px 30px rgba(0,0,0,0.2)", padding: 14 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ fontWeight: 800, fontSize: "1.1rem" }}>Admin-Bereich</div>
              <button onClick={() => setIsAdminOpen(false)} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #ccc", background: "#fff", cursor: "pointer" }}>✕</button>
            </div>
            <div style={{ marginTop: 12 }}>
              <AdminPanel auth={auth} authHeaders={authHeaders} me={me} />
            </div>
          </div>
        </div>
      )}

      {toast && (
        <Toast kind={toast.kind} message={toast.message} onClose={() => setToast(null)} onAction={() => { setSelectedCaseId(toast.caseId); setToast(null); }} actionLabel="Öffnen" />
      )}
    </main>
  );
}
