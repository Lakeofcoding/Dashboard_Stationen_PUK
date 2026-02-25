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

import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import type { CaseSummary, CaseDetail, Severity, DayState } from "./types";
import { AdminPanel } from "./AdminPanel";
import ParameterBar from "./ParameterBar";
import CaseTable from "./CaseTable";
import MatrixReport from "./MatrixReport";
import MonitoringPanel from "./MonitoringPanel";

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
    stationId: localStorage.getItem(LS_KEYS.stationId) ?? "Station A1",
    userId: localStorage.getItem(LS_KEYS.userId) ?? "demo",
  };
}

function saveAuth(a: AuthState) {
  localStorage.setItem(LS_KEYS.stationId, a.stationId);
  localStorage.setItem(LS_KEYS.userId, a.userId);
}

function authHeaders(auth: AuthState): HeadersInit {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Station-Id": auth.stationId,
    "X-User-Id": auth.userId,
  };
  // CSRF-Token aus Cookie lesen und als Header mitsenden
  const csrf = document.cookie.split("; ").find(c => c.startsWith("csrf_token="));
  if (csrf) {
    h["X-CSRF-Token"] = csrf.split("=")[1];
  }
  return h;
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

class SessionExpiredError extends Error {
  constructor(msg: string) { super(msg); this.name = "SessionExpiredError"; }
}

async function apiJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(withCtx(path, init), init);
  if (res.status === 403 || res.status === 401) {
    const text = await res.text().catch(() => "");
    // Check if it's a session/auth issue vs permission issue
    const lower = text.toLowerCase();
    if (lower.includes("user disabled") || lower.includes("unknown user") || lower.includes("session")) {
      throw new SessionExpiredError(text || "Sitzung abgelaufen");
    }
    throw new Error(text || `Keine Berechtigung (${res.status})`);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

type ViewMode = "overview" | "cases" | "report" | "monitoring" | "admin";
type CategoryFilter = "all" | "completeness" | "medical";

type StationOverviewItem = {
  station_id: string;
  center: string;
  clinic: string;
  total_cases: number;
  open_cases: number;
  critical_count: number;
  warn_count: number;
  ok_count: number;
  severity: Severity;
  // Per-category
  completeness_critical?: number;
  completeness_warn?: number;
  completeness_severity?: Severity;
  medical_critical?: number;
  medical_warn?: number;
  medical_severity?: Severity;
};

async function fetchOverview(auth: AuthState): Promise<StationOverviewItem[]> {
  return apiJson<StationOverviewItem[]>("/api/overview", {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function fetchCases(auth: AuthState, _view: ViewMode): Promise<CaseSummary[]> {
  const qs = new URLSearchParams({ view: "all" }).toString();
  return apiJson<CaseSummary[]>(`/api/cases?${qs}`, {
    method: "GET",
    headers: authHeaders(auth),
  });
}

async function fetchCaseDetail(caseId: string, auth: AuthState, _view: ViewMode): Promise<CaseDetail> {
  const qs = new URLSearchParams({ view: "all" }).toString();
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

  const [stations, setStations] = useState<string[]>(["Station A1", "Station B0", "Station B2"]);
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

  // Session timeout: 30 min inactivity
  const SESSION_TIMEOUT_MS = 30 * 60 * 1000;
  const SESSION_WARNING_MS = 28 * 60 * 1000; // warn 2 min before
  const lastActivityRef = useRef(Date.now());
  const [sessionExpired, setSessionExpired] = useState(false);
  const [sessionWarning, setSessionWarning] = useState(false);

  // Track user activity
  useEffect(() => {
    const touch = () => { lastActivityRef.current = Date.now(); setSessionWarning(false); };
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    events.forEach(e => window.addEventListener(e, touch, { passive: true }));
    // Check timeout every 30s
    const timer = window.setInterval(() => {
      const idle = Date.now() - lastActivityRef.current;
      if (idle >= SESSION_TIMEOUT_MS) {
        setSessionExpired(true);
      } else if (idle >= SESSION_WARNING_MS) {
        setSessionWarning(true);
      }
    }, 30_000);
    return () => {
      events.forEach(e => window.removeEventListener(e, touch));
      window.clearInterval(timer);
    };
  }, []);

  const [viewMode, setViewMode] = useState<ViewMode>("overview");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");
  const [dayState, setDayState] = useState<DayState | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [overview, setOverview] = useState<StationOverviewItem[]>([]);
  const [drillClinic, setDrillClinic] = useState<string | null>(null);
  const [drillCenter, setDrillCenter] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [shiftByAlert, setShiftByAlert] = useState<Record<string, string>>({});

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

  // Load cases + day state (skip when in overview mode)
  useEffect(() => {
    if (viewMode === "overview") return;
    let alive = true;
    const load = async () => {
      try {
        const [data, ds] = await Promise.all([fetchCases(auth, "cases"), fetchDayState(auth)]);
        if (!alive) return;
        setCases(data);
        setDayState(ds);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message ?? String(e));
      }
    };
    load();
    const id = window.setInterval(load, 10_000);
    return () => { alive = false; window.clearInterval(id); };
  }, [auth, viewMode]);

  // Load overview data
  useEffect(() => {
    if (viewMode !== "overview") return;
    let alive = true;
    const load = async () => {
      try {
        const data = await fetchOverview(auth);
        if (alive) { setOverview(data); setError(null); }
      } catch (e: any) {
        if (alive) setError(e?.message ?? String(e));
      }
    };
    load();
    const id = window.setInterval(load, 15_000);
    return () => { alive = false; window.clearInterval(id); };
  }, [auth, viewMode]);

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

  // ── Hierarchische Aggregation: Klinik → Zentrum → Station ──
  const CLINIC_LABELS: Record<string, string> = {
    APP: "Alterspsychiatrie",
    EPP: "Erwachsenenpsychiatrie",
    FPP: "Forensische Psychiatrie",
    KJPP: "Kinder- und Jugendpsychiatrie",
  };

  type AggItem = { total: number; open: number; closed: number; critical: number; warn: number; ok: number; severity: Severity };
  const aggregate = (items: StationOverviewItem[]): AggItem => {
    const total = items.reduce((s, i) => s + i.total_cases, 0);
    const open = items.reduce((s, i) => s + i.open_cases, 0);
    // Use per-category counts when filtered
    const critical = items.reduce((s, i) => s + (
      categoryFilter === "completeness" ? (i.completeness_critical ?? i.critical_count)
      : categoryFilter === "medical" ? (i.medical_critical ?? i.critical_count)
      : i.critical_count
    ), 0);
    const warn = items.reduce((s, i) => s + (
      categoryFilter === "completeness" ? (i.completeness_warn ?? i.warn_count)
      : categoryFilter === "medical" ? (i.medical_warn ?? i.warn_count)
      : i.warn_count
    ), 0);
    const ok = total - critical - warn;
    const severity: Severity = critical > 0 ? "CRITICAL" : warn > 0 ? "WARN" : "OK";
    return { total, open, closed: total - open, critical, warn, ok, severity };
  };

  const clinicGroups = useMemo(() => {
    const map: Record<string, StationOverviewItem[]> = {};
    for (const s of overview) map[s.clinic] = [...(map[s.clinic] || []), s];
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [overview]);

  const centerGroups = useMemo(() => {
    if (!drillClinic) return [];
    const items = overview.filter(s => s.clinic === drillClinic);
    const map: Record<string, StationOverviewItem[]> = {};
    for (const s of items) map[s.center] = [...(map[s.center] || []), s];
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b));
  }, [overview, drillClinic]);

  const stationItems = useMemo(() => {
    if (!drillClinic || !drillCenter) return [];
    return overview.filter(s => s.clinic === drillClinic && s.center === drillCenter);
  }, [overview, drillClinic, drillCenter]);

  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh", width: "100vw", overflow: "hidden", fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial", backgroundColor: "#f4f7f6" }}>
      {/* SESSION EXPIRED OVERLAY */}
      {sessionExpired && (
        <div style={{ position: "fixed", inset: 0, zIndex: 9999, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}>
          <div style={{ background: "#fff", borderRadius: 16, padding: "32px 40px", maxWidth: 420, textAlign: "center", boxShadow: "0 20px 60px rgba(0,0,0,0.3)" }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔒</div>
            <h2 style={{ margin: "0 0 8px 0", fontSize: 18 }}>Sitzung abgelaufen</h2>
            <p style={{ color: "#6b7280", fontSize: 14, margin: "0 0 20px 0" }}>
              Aus Sicherheitsgründen wurde Ihre Sitzung nach 30 Minuten Inaktivität beendet.
              Patientendaten werden nicht mehr aktualisiert.
            </p>
            <button
              onClick={() => { lastActivityRef.current = Date.now(); setSessionExpired(false); setSessionWarning(false); window.location.reload(); }}
              style={{ padding: "10px 28px", borderRadius: 8, border: "none", background: "#3b82f6", color: "#fff", fontWeight: 700, fontSize: 14, cursor: "pointer" }}
            >
              Neu anmelden
            </button>
          </div>
        </div>
      )}

      {/* SESSION WARNING BANNER */}
      {sessionWarning && !sessionExpired && (
        <div style={{ padding: "8px 20px", background: "#fef3c7", borderBottom: "1px solid #fcd34d", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13, color: "#92400e", zIndex: 200 }}>
          <span>⏱ Ihre Sitzung läuft in Kürze ab. Bewegen Sie die Maus, um aktiv zu bleiben.</span>
          <button onClick={() => { lastActivityRef.current = Date.now(); setSessionWarning(false); }} style={{ padding: "4px 12px", borderRadius: 6, border: "1px solid #d97706", background: "#fff", color: "#92400e", fontWeight: 600, fontSize: 12, cursor: "pointer" }}>
            Sitzung verlängern
          </button>
        </div>
      )}

      {/* HEADER */}
      <header style={{ backgroundColor: "#fff", borderBottom: "1px solid #e5e7eb", boxShadow: "0 1px 3px rgba(0,0,0,0.05)", zIndex: 100 }}>
        {/* Top row: Logo + Controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 20px", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <h1 style={{ margin: 0, fontSize: "1.15rem", color: "#1a1a1a", fontWeight: 800 }}>PUK Dashboard</h1>
            <div style={{ flexShrink: 0 }}><ClinicLogo title="Klinik-Logo" /></div>
            <label style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: 8 }}>
              <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 600 }}>Station</span>
              <select value={auth.stationId} onChange={(e) => updateAuth({ stationId: e.target.value })} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
                {stations.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
            <label style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ fontSize: 11, color: "#6b7280", fontWeight: 600 }}>User</span>
              <select value={auth.userId} onChange={(e) => updateAuth({ userId: e.target.value })} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 12, cursor: "pointer" }}>
                {metaUsers.map((u) => <option key={u.user_id} value={u.user_id}>{u.user_id}</option>)}
              </select>
            </label>
            {dayState && <span style={{ color: "#9ca3af", fontSize: 11 }}>Tag: {dayState.business_date} · V{dayState.version}</span>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button
              onClick={async () => {
                if (!canReset) return;
                if (!window.confirm(`Alle heutigen Quittierungen für Station ${auth.stationId} zurücksetzen?`)) return;
                try {
                  const ds = await resetToday(auth);
                  setDayState(ds);
                  const data = await fetchCases(auth, viewMode);
                  setCases(data);
                  setSelectedCaseId(null); setDetail(null); setDetailError(null); setShiftByAlert({});
                } catch (e: any) { setError(e?.message ?? String(e)); }
              }}
              disabled={!canReset}
              style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: canReset ? "pointer" : "not-allowed", opacity: canReset ? 1 : 0.5 }}
            >
              Reset
            </button>
            <button onClick={() => setIsAdminOpen(true)} disabled={!canAdmin} style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: canAdmin ? "pointer" : "not-allowed", opacity: canAdmin ? 1 : 0.5 }}>
              ⚙ Admin
            </button>
            <div style={{ fontSize: 11, textAlign: "right", color: "#6b7280", display: "flex", alignItems: "center", gap: 8 }}>
              {/* Role badge */}
              {me && me.roles.length > 0 && (
                <span style={{ padding: "2px 7px", borderRadius: 999, fontSize: 10, fontWeight: 600, background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe" }}>
                  {me.roles.includes("system_admin") ? "System Admin"
                    : me.roles.includes("admin") ? "Admin"
                    : me.roles.includes("shift_lead") ? "Schichtleitung"
                    : me.roles.includes("clinician") ? "Klinisch"
                    : me.roles.includes("manager") ? "Management"
                    : me.roles[0]}
                </span>
              )}
              {/* Break-glass warning */}
              {me?.break_glass && (
                <span style={{ padding: "2px 7px", borderRadius: 999, fontSize: 10, fontWeight: 700, background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca", animation: "pulse 2s infinite" }}>
                  🔓 Break-Glass
                </span>
              )}
              {/* User + Station context */}
              <span style={{ fontWeight: 700, color: "#374151" }}>{me?.user_id || auth.userId}</span>
              <span style={{ color: "#9ca3af" }}>@ {auth.stationId}</span>
            </div>
          </div>
        </div>

        {/* Tab Bar */}
        <nav style={{ display: "flex", gap: 0, paddingLeft: 20, borderTop: "1px solid #f3f4f6" }}>
          {([
            { key: "overview", label: "Übersicht", icon: "📋" },
            { key: "cases", label: "Fallliste", icon: "🏥" },
            { key: "report", label: "Tagesbericht", icon: "📊" },
            { key: "monitoring", label: "Monitoring", icon: "📈" },
          ] as { key: ViewMode; label: string; icon: string }[]).map((tab) => {
            const isActive = viewMode === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => {
                  setViewMode(tab.key);
                  if (tab.key === "overview") { setSelectedCaseId(null); setDetail(null); setDrillClinic(null); setDrillCenter(null); }
                }}
                style={{
                  padding: "10px 18px",
                  fontSize: 13,
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? "#1d4ed8" : "#6b7280",
                  background: "transparent",
                  border: "none",
                  borderBottom: isActive ? "2px solid #3b82f6" : "2px solid transparent",
                  cursor: "pointer",
                  transition: "all 0.15s",
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                }}
              >
                <span style={{ fontSize: 14 }}>{tab.icon}</span>
                {tab.label}
              </button>
            );
          })}
        </nav>
      </header>

      {metaError ? <div style={{ padding: "10px 16px", color: "#666", background: "#fff", borderBottom: "1px solid #eee" }}>{metaError}</div> : null}
      {error && <div style={{ padding: "10px 16px", color: "#b42318", background: "#fff", borderBottom: "1px solid #eee" }}>Fehler: {error}</div>}

      {/* ═══ Kategorie-Filter (Dokumentation / Klinisch / Alle) ═══ */}
      {viewMode !== "admin" && (
        <div style={{ padding: "6px 20px", background: "#f9fafb", borderBottom: "1px solid #e5e7eb", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#6b7280", marginRight: 4 }}>Ansicht:</span>
          {([
            { key: "all" as CategoryFilter, label: "Alle", icon: "⊞" },
            { key: "completeness" as CategoryFilter, label: "Dokumentation", icon: "📋" },
            { key: "medical" as CategoryFilter, label: "Klinisch", icon: "🩺" },
          ]).map((f) => {
            const active = categoryFilter === f.key;
            return (
              <button
                key={f.key}
                onClick={() => setCategoryFilter(f.key)}
                style={{
                  padding: "4px 12px", fontSize: 12, fontWeight: active ? 700 : 500, borderRadius: 6,
                  background: active ? (f.key === "completeness" ? "#dbeafe" : f.key === "medical" ? "#fce7f3" : "#e5e7eb") : "transparent",
                  color: active ? (f.key === "completeness" ? "#1d4ed8" : f.key === "medical" ? "#be185d" : "#374151") : "#6b7280",
                  border: active ? "1px solid" : "1px solid transparent",
                  borderColor: active ? (f.key === "completeness" ? "#93c5fd" : f.key === "medical" ? "#f9a8d4" : "#d1d5db") : "transparent",
                  cursor: "pointer", transition: "all 0.15s",
                }}
              >
                <span style={{ marginRight: 4 }}>{f.icon}</span>{f.label}
              </button>
            );
          })}
        </div>
      )}

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>

        {/* ─── TAB: ÜBERSICHT (Klinik → Zentrum → Station) ─── */}
        {viewMode === "overview" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
            <div style={{ maxWidth: 1200, margin: "0 auto" }}>

              {/* Breadcrumb */}
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 16, fontSize: 13, color: "#6b7280" }}>
                <span
                  onClick={() => { setDrillClinic(null); setDrillCenter(null); }}
                  style={{ cursor: "pointer", fontWeight: !drillClinic ? 700 : 400, color: !drillClinic ? "#1d4ed8" : "#6b7280" }}
                >
                  Kliniken
                </span>
                {drillClinic && (
                  <>
                    <span style={{ color: "#d1d5db" }}>/</span>
                    <span
                      onClick={() => setDrillCenter(null)}
                      style={{ cursor: "pointer", fontWeight: !drillCenter ? 700 : 400, color: !drillCenter ? "#1d4ed8" : "#6b7280" }}
                    >
                      {drillClinic}
                    </span>
                  </>
                )}
                {drillCenter && (
                  <>
                    <span style={{ color: "#d1d5db" }}>/</span>
                    <span style={{ fontWeight: 700, color: "#1d4ed8" }}>{drillCenter}</span>
                  </>
                )}
              </div>

              {overview.length === 0 ? (
                <div style={{ color: "#9ca3af", padding: 20 }}>Lade Übersicht…</div>
              ) : !drillClinic ? (
                /* ── LEVEL 1: Kliniken ── */
                <>
                  <h2 style={{ margin: "0 0 16px 0", fontSize: "1.2rem" }}>Kliniken</h2>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
                    {clinicGroups.map(([clinic, items]) => {
                      const a = aggregate(items);
                      const centerCount = new Set(items.map(i => i.center)).size;
                      return (
                        <div
                          key={clinic}
                          onClick={() => setDrillClinic(clinic)}
                          style={{
                            padding: 20, borderRadius: 12,
                            background: severityColor(a.severity),
                            border: `2px solid ${severityBorderColor(a.severity)}`,
                            cursor: "pointer", transition: "transform 0.15s, box-shadow 0.15s",
                          }}
                          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.1)"; }}
                          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = ""; (e.currentTarget as HTMLElement).style.boxShadow = ""; }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                            <div>
                              <div style={{ fontSize: "1.4rem", fontWeight: 800, letterSpacing: "0.5px" }}>{clinic}</div>
                              <div style={{ fontSize: 12, color: "#6b7280", marginTop: 2 }}>{CLINIC_LABELS[clinic] || clinic}</div>
                            </div>
                            <div style={{
                              width: 40, height: 40, borderRadius: "50%",
                              background: a.severity === "CRITICAL" ? "#ef4444" : a.severity === "WARN" ? "#f59e0b" : "#22c55e",
                              display: "flex", alignItems: "center", justifyContent: "center",
                              color: "#fff", fontWeight: 800, fontSize: 16,
                            }}>
                              {a.severity === "CRITICAL" ? "!" : a.severity === "WARN" ? "⚠" : "✓"}
                            </div>
                          </div>
                          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 16px", fontSize: 13, color: "#374151" }}>
                            <span>Fälle gesamt: <strong>{a.total}</strong></span>
                            <span>Offen: <strong>{a.open}</strong></span>
                            <span>Zentren: <strong>{centerCount}</strong></span>
                            <span>Stationen: <strong>{items.length}</strong></span>
                          </div>
                          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                            {a.critical > 0 && <span style={{ fontSize: 11, background: "#ef4444", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{a.critical} kritisch</span>}
                            {a.warn > 0 && <span style={{ fontSize: 11, background: "#f59e0b", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{a.warn} Warn.</span>}
                            {a.ok > 0 && <span style={{ fontSize: 11, background: "#22c55e", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{a.ok} OK</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : !drillCenter ? (
                /* ── LEVEL 2: Zentren einer Klinik ── */
                <>
                  <h2 style={{ margin: "0 0 16px 0", fontSize: "1.2rem" }}>
                    Zentren – {drillClinic} <span style={{ fontWeight: 400, fontSize: 14, color: "#6b7280" }}>({CLINIC_LABELS[drillClinic] || ""})</span>
                  </h2>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
                    {centerGroups.map(([center, items]) => {
                      const a = aggregate(items);
                      return (
                        <div
                          key={center}
                          onClick={() => setDrillCenter(center)}
                          style={{
                            padding: 18, borderRadius: 10,
                            background: severityColor(a.severity),
                            border: `2px solid ${severityBorderColor(a.severity)}`,
                            cursor: "pointer", transition: "transform 0.15s, box-shadow 0.15s",
                          }}
                          onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.1)"; }}
                          onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = ""; (e.currentTarget as HTMLElement).style.boxShadow = ""; }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                            <div>
                              <div style={{ fontSize: "1.2rem", fontWeight: 800 }}>{center}</div>
                              <div style={{ fontSize: 11, color: "#6b7280" }}>{items.length} Station{items.length !== 1 ? "en" : ""}</div>
                            </div>
                            <div style={{
                              width: 36, height: 36, borderRadius: "50%",
                              background: a.severity === "CRITICAL" ? "#ef4444" : a.severity === "WARN" ? "#f59e0b" : "#22c55e",
                              display: "flex", alignItems: "center", justifyContent: "center",
                              color: "#fff", fontWeight: 800, fontSize: 15,
                            }}>
                              {a.severity === "CRITICAL" ? "!" : a.severity === "WARN" ? "⚠" : "✓"}
                            </div>
                          </div>
                          <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#374151" }}>
                            <span>Fälle: <strong>{a.total}</strong></span>
                            <span>Offen: <strong>{a.open}</strong></span>
                          </div>
                          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                            {a.critical > 0 && <span style={{ fontSize: 11, background: "#ef4444", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{a.critical} kritisch</span>}
                            {a.warn > 0 && <span style={{ fontSize: 11, background: "#f59e0b", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{a.warn} Warn.</span>}
                            {a.critical === 0 && a.warn === 0 && <span style={{ fontSize: 11, background: "#22c55e", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>OK</span>}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              ) : (
                /* ── LEVEL 3: Stationen eines Zentrums ── */
                <>
                  <h2 style={{ margin: "0 0 16px 0", fontSize: "1.2rem" }}>
                    Stationen – {drillCenter}
                  </h2>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
                    {stationItems.map((s) => {
                      const eSev = categoryFilter === "completeness" ? (s.completeness_severity ?? s.severity)
                        : categoryFilter === "medical" ? (s.medical_severity ?? s.severity) : s.severity;
                      return (
                      <div
                        key={s.station_id}
                        onClick={() => { updateAuth({ stationId: s.station_id }); setViewMode("cases"); }}
                        style={{
                          padding: 16, borderRadius: 10,
                          background: severityColor(eSev),
                          border: `2px solid ${severityBorderColor(eSev)}`,
                          cursor: "pointer", transition: "transform 0.15s, box-shadow 0.15s",
                        }}
                        onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)"; (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 16px rgba(0,0,0,0.1)"; }}
                        onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = ""; (e.currentTarget as HTMLElement).style.boxShadow = ""; }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                          <div>
                            <div style={{ fontSize: "1.2rem", fontWeight: 800 }}>{s.station_id}</div>
                            <div style={{ fontSize: 11, color: "#6b7280" }}>{s.center}</div>
                          </div>
                          <div style={{
                            width: 36, height: 36, borderRadius: "50%",
                            background: eSev === "CRITICAL" ? "#ef4444" : eSev === "WARN" ? "#f59e0b" : "#22c55e",
                            display: "flex", alignItems: "center", justifyContent: "center",
                            color: "#fff", fontWeight: 800, fontSize: 15,
                          }}>
                            {eSev === "CRITICAL" ? "!" : eSev === "WARN" ? "⚠" : "✓"}
                          </div>
                        </div>
                        <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#374151" }}>
                          <span>Fälle: <strong>{s.total_cases}</strong></span>
                          <span>Offen: <strong>{s.open_cases}</strong></span>
                        </div>
                        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                          {s.critical_count > 0 && <span style={{ fontSize: 11, background: "#ef4444", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{s.critical_count} kritisch</span>}
                          {s.warn_count > 0 && <span style={{ fontSize: 11, background: "#f59e0b", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>{s.warn_count} Warn.</span>}
                          {s.critical_count === 0 && s.warn_count === 0 && <span style={{ fontSize: 11, background: "#22c55e", color: "#fff", padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>OK</span>}
                        </div>
                      </div>
                      );
                    })}
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* ─── TAB: FALLLISTE (sortierbare Tabelle + Detail) ─── */}
        {viewMode === "cases" && (
          <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
            {/* Left: sortable table */}
            <div style={{ flex: selectedCaseId ? "0 0 55%" : 1, overflowY: "auto", borderRight: selectedCaseId ? "1px solid #e5e7eb" : "none" }}>
              <CaseTable
                cases={cases}
                selectedCaseId={selectedCaseId}
                onSelectCase={setSelectedCaseId}
                parameterFilter={categoryFilter}
              />
            </div>
            {/* Right: detail panel */}
            {selectedCaseId && (
              <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
                {detailLoading && <div style={{ color: "#9ca3af", fontSize: 12 }}>Lädt…</div>}
                {detailError && <div style={{ color: "#dc2626" }}>Fehler: {detailError}</div>}
                {detail && <DetailPanel
                  detail={detail}
                  canAck={canAck}
                  shiftByAlert={shiftByAlert}
                  shiftReasons={shiftReasons}
                  categoryFilter={categoryFilter}
                  onSetShift={setShift}
                  onAckRule={async (caseId, ruleId) => {
                    await ackRule(caseId, ruleId, auth);
                    const [newList, newDetail] = await Promise.all([fetchCases(auth, viewMode), fetchCaseDetail(caseId, auth, viewMode)]);
                    setCases(newList); setDetail(newDetail);
                  }}
                  onShiftRule={async (caseId, ruleId, shiftVal) => {
                    await shiftRule(caseId, ruleId, shiftVal, auth);
                    setShift(caseId, ruleId, "");
                    const [newList, newDetail] = await Promise.all([fetchCases(auth, viewMode), fetchCaseDetail(caseId, auth, viewMode)]);
                    setCases(newList); setDetail(newDetail);
                  }}
                  onError={(msg) => setError(msg)}
                />}
              </div>
            )}
          </div>
        )}

        {/* ─── TAB: TAGESBERICHT (Matrix-Heatmap) ─── */}
        {viewMode === "report" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
            <div style={{ maxWidth: 1400, margin: "0 auto" }}>
              <MatrixReport
                cases={cases}
                onSelectCase={(id) => { setSelectedCaseId(id); setViewMode("cases"); }}
                authHeaders={authHeaders(auth) as Record<string, string>}
                categoryFilter={categoryFilter}
              />
            </div>
          </div>
        )}

        {/* ─── TAB: MONITORING (Sparklines + Detail-Charts) ─── */}
        {viewMode === "monitoring" && (
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>
            <div style={{ maxWidth: 1400, margin: "0 auto" }}>
              <MonitoringPanel
                cases={cases}
                selectedCaseId={selectedCaseId}
                onSelectCase={setSelectedCaseId}
              />
            </div>
          </div>
        )}
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

    </main>
  );
}

/* ═══════════════════════════════════════════
   DetailPanel – Extracted from inline JSX
   ═══════════════════════════════════════════ */
interface DetailPanelProps {
  detail: CaseDetail;
  canAck: boolean;
  shiftByAlert: Record<string, string>;
  shiftReasons: ShiftReason[];
  categoryFilter: "all" | "completeness" | "medical";
  onSetShift: (caseId: string, ruleId: string, value: string) => void;
  onAckRule: (caseId: string, ruleId: string) => Promise<void>;
  onShiftRule: (caseId: string, ruleId: string, shiftVal: string) => Promise<void>;
  onError: (msg: string) => void;
}

function DetailPanel({ detail, canAck, shiftByAlert, shiftReasons, categoryFilter, onSetShift, onAckRule, onShiftRule, onError }: DetailPanelProps) {
  const filteredAlerts = categoryFilter === "all"
    ? detail.alerts
    : detail.alerts.filter(a => a.category === categoryFilter);
  const filteredParams = categoryFilter === "all"
    ? (detail.parameter_status ?? [])
    : (detail.parameter_status ?? []).filter(p => p.group === categoryFilter);

  return (
    <div style={{ maxWidth: 980 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.15rem" }}>Fall: {detail.case_id}</h2>
          <p style={{ color: "#6b7280", margin: "4px 0 0", fontSize: 13 }}>Station: {detail.station_id}</p>
        </div>
        {!!(detail as any).break_glass_active && (
          <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", padding: "6px 12px", borderRadius: 8, color: "#dc2626", fontWeight: 800, fontSize: 12 }}>
            NOTFALLZUGRIFF AKTIV
          </div>
        )}
      </div>

      {/* Info Cards */}
      <div style={{ marginBottom: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
        <div style={{ padding: 10, borderRadius: 8, background: "#f9fafb", border: "1px solid #e5e7eb" }}>
          <div style={{ fontSize: 10, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>Fall</div>
          <div style={{ fontSize: 12 }}><strong>Eintritt:</strong> {(detail as any).admission_date ?? "—"}</div>
          <div style={{ fontSize: 12, color: detail.discharge_date ? "#374151" : "#2563eb", fontWeight: detail.discharge_date ? 400 : 600 }}>
            <strong>Austritt:</strong> {detail.discharge_date ?? "Offener Fall"}
          </div>
          {detail.case_status && (
            <div style={{ fontSize: 12, marginTop: 2 }}><strong>Status:</strong> {detail.case_status}</div>
          )}
          {detail.responsible_person && (
            <div style={{ fontSize: 12, marginTop: 2 }}><strong>Fallführung:</strong> {detail.responsible_person}</div>
          )}
        </div>
        <div style={{ padding: 10, borderRadius: 8, background: "#f9fafb", border: "1px solid #e5e7eb" }}>
          <div style={{ fontSize: 10, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>Scores</div>
          <div style={{ fontSize: 12 }}><strong>HoNOS:</strong> {(detail as any).honos ?? "—"}</div>
          <div style={{ fontSize: 12 }}><strong>BSCL:</strong> {(detail as any).bscl ?? "—"}</div>
        </div>
        <div style={{ padding: 10, borderRadius: 8, background: "#f9fafb", border: "1px solid #e5e7eb" }}>
          <div style={{ fontSize: 10, color: "#6b7280", fontWeight: 600, textTransform: "uppercase", marginBottom: 4 }}>Dokumentation</div>
          <div style={{ fontSize: 12 }}><strong>BFS:</strong> {(detail as any).bfs_complete ? "✓ Vollständig" : "✕ Unvollständig"}</div>
          <div style={{ fontSize: 12 }}><strong>Status:</strong> {detail.severity === "OK" ? "✓ OK" : detail.severity}</div>
        </div>
      </div>

      {/* Parameter Status */}
      {filteredParams.length > 0 && (
        <div style={{ marginBottom: 14, padding: 12, borderRadius: 8, background: "#fff", border: "1px solid #e5e7eb" }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: "#374151", marginBottom: 6 }}>Parameter-Übersicht</div>
          <ParameterBar parameters={filteredParams} compact={false} showGroupLabels={categoryFilter === "all"} />
        </div>
      )}

      {/* Alerts */}
      <h3 style={{ margin: "0 0 8px 0", fontSize: "0.95rem" }}>
        Alerts
        {categoryFilter !== "all" && (
          <span style={{ fontSize: 12, fontWeight: 400, color: "#6b7280", marginLeft: 8 }}>
            ({categoryFilter === "completeness" ? "📋 Dokumentation" : "🩺 Klinisch"})
          </span>
        )}
      </h3>
      {filteredAlerts.length === 0 ? (
        <div style={{ color: "#16a34a", padding: 14, background: "#f0fdf4", borderRadius: 8, fontSize: 13 }}>
          ✓ Keine offenen Alerts.
        </div>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {filteredAlerts.map((a) => {
            const key = `${detail.case_id}::${a.rule_id}`;
            const shiftVal = shiftByAlert[key] ?? "";
            return (
              <div
                key={a.rule_id}
                style={{
                  padding: 12, borderRadius: 8,
                  backgroundColor: severityColor(a.severity),
                  border: `1px solid ${severityBorderColor(a.severity)}40`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 13 }}>{(a as any).message ?? a.rule_id}</div>
                    {(a as any).explanation && (
                      <div style={{ fontSize: 12, color: "#4b5563", marginTop: 3 }}>{(a as any).explanation}</div>
                    )}
                    <div style={{ fontSize: 10, color: "#9ca3af", marginTop: 3 }}>
                      {a.category === "completeness" ? "📋 Vollständigkeit" : "🏥 Medizinisch"} · {a.severity}
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                    <select
                      disabled={!canAck}
                      value={shiftVal}
                      onChange={(e) => onSetShift(detail.case_id, a.rule_id, e.target.value)}
                      style={{ padding: "4px 6px", borderRadius: 6, border: "1px solid #d1d5db", fontSize: 11, cursor: canAck ? "pointer" : "not-allowed", maxWidth: 140 }}
                    >
                      <option value="">Erinnern…</option>
                      {shiftReasons.map((r) => (
                        <option key={r.code} value={r.code}>{r.code}: {r.label}</option>
                      ))}
                    </select>
                    <button
                      disabled={!canAck || !shiftVal}
                      onClick={async () => {
                        try { await onShiftRule(detail.case_id, a.rule_id, shiftVal); }
                        catch (e: any) { onError(e?.message ?? String(e)); }
                      }}
                      style={{ padding: "4px 8px", fontSize: 11, borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: canAck && shiftVal ? "pointer" : "not-allowed", opacity: canAck && shiftVal ? 1 : 0.5 }}
                    >
                      Erinnern
                    </button>
                    <button
                      disabled={!canAck}
                      onClick={async () => {
                        try { await onAckRule(detail.case_id, a.rule_id); }
                        catch (e: any) { onError(e?.message ?? String(e)); }
                      }}
                      style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "none", background: canAck ? "#1f2937" : "#9ca3af", color: "#fff", fontWeight: 700, cursor: canAck ? "pointer" : "not-allowed" }}
                    >
                      {ackLabel(a.category)}
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
