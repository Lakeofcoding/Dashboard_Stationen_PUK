import { useEffect, useMemo, useRef, useState } from "react";
import type { CaseDetail, CaseSummary, Severity } from "./types";
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

function loadAuth(): AuthState {
  return {
    stationId: localStorage.getItem(LS_KEYS.stationId) ?? "B0",
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

  // harte Diagnosehilfe: wenn HTML zurückkommt, ist Proxy/URL falsch
  const contentType = res.headers.get("content-type") ?? "";
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  if (!contentType.includes("application/json")) {
    const text = await res.text().catch(() => "");
    throw new Error(`Backend lieferte kein JSON (Content-Type: ${contentType}). Anfang: ${text.slice(0, 40)}`);
  }

  return (await res.json()) as T;
}

async function fetchCases(auth: AuthState): Promise<CaseSummary[]> {
  return apiJson<CaseSummary[]>("/api/cases", { method: "GET", headers: authHeaders(auth) });
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

function severityPill(sev: Severity) {
  if (sev === "CRITICAL") return "bg-red-50 text-red-700 ring-1 ring-red-100";
  if (sev === "WARN") return "bg-amber-50 text-amber-800 ring-1 ring-amber-100";
  return "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100";
}

export default function App() {
  // Branding-Placeholder (wie von dir gewünscht)
  const clinicName = "Psychiatrische Universitätsklinik Zürich";
  const clinicCode = "EPP";
  const centerCode = "ZAPE";

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
  const shownCriticalRef = useRef<Record<string, true>>({});

  function updateAuth(patch: Partial<AuthState>) {
    const next = { ...auth, ...patch };
    setAuth(next);
    saveAuth(next);
  }

  function splitRoles(rolesCsv: string): string[] {
    return rolesCsv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  // Meta endpoints (optional)
  useEffect(() => {
    let alive = true;

    (async () => {
      try {
        const st = await fetch("/api/meta/stations").then((r) =>
          r.ok ? r.json() : Promise.reject(new Error("meta/stations"))
        );
        if (alive && Array.isArray(st?.stations) && st.stations.length) {
          setStations(st.stations);
          if (!st.stations.includes(auth.stationId)) updateAuth({ stationId: st.stations[0] });
        }
      } catch {
        // ignore
      }

      try {
        const us = await fetch("/api/meta/users").then((r) =>
          r.ok ? r.json() : Promise.reject(new Error("meta/users"))
        );
        if (alive && Array.isArray(us?.users) && us.users.length) {
          setMetaUsers(us.users);
          const u = us.users.find((x: MetaUser) => x.user_id === auth.userId) ?? us.users[0];
          if (u) updateAuth({ userId: u.user_id, rolesCsv: (u.roles ?? []).join(",") });
        }
      } catch {
        if (alive) setMetaError("Meta-Endpoints nicht erreichbar (Fallback aktiv).");
      }
    })();

    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Rollen aus Meta ableiten (kein Freitext)
  useEffect(() => {
    const u = metaUsers.find((x) => x.user_id === auth.userId);
    if (u) {
      const next = (u.roles ?? []).join(",");
      if (next && next !== auth.rolesCsv) updateAuth({ rolesCsv: next });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.userId, metaUsers]);

  // Poll list
  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const data = await fetchCases(auth);
        if (!alive) return;
        setCases(data);
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

    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [auth, toast]);

  // Load detail
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
      .catch((err) => {
        setDetail(null);
        setDetailError(err?.message ?? String(err));
      })
      .finally(() => setDetailLoading(false));
  }, [selectedCaseId, auth]);

  // Sync ack status from list
  useEffect(() => {
    if (!detail || !selectedCaseId) return;
    const fromList = cases.find((c) => c.case_id === selectedCaseId);
    if (!fromList) return;
    if (fromList.acked_at !== detail.acked_at) setDetail({ ...detail, acked_at: fromList.acked_at });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cases, selectedCaseId]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-6 py-5">
          <div className="flex items-start justify-between gap-6">
            <div className="flex items-start gap-4">
              <div className="grid h-11 w-11 place-items-center rounded-2xl bg-slate-900 text-sm font-semibold text-white">
                {clinicCode}
              </div>

              <div className="min-w-0">
                <div className="text-xl font-semibold tracking-tight">{clinicName}</div>
                <div className="mt-0.5 text-sm text-slate-600">Dashboard Stationsmonitoring</div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                    Klinik: <span className="ml-1 font-medium">{clinicCode}</span>
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                    Zentrum: <span className="ml-1 font-medium">{centerCode}</span>
                  </span>
                  <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-3 py-1">
                    Station: <span className="ml-1 font-medium">{auth.stationId}</span>
                  </span>
                </div>
              </div>
            </div>

            <div className="hidden text-right text-xs text-slate-500 md:block">
              <div>
                User: <code className="rounded bg-slate-100 px-1 py-0.5">{auth.userId}</code>
              </div>
              <div className="mt-1">
                Rollen:{" "}
                <code className="rounded bg-slate-100 px-1 py-0.5">{auth.rolesCsv || "—"}</code>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto max-w-7xl px-6 py-6">
        {error && (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            Fehler: {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_420px]">
          {/* LEFT */}
          <section className="space-y-3">
            {/* Kontext */}
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="grid gap-1 text-sm">
                    <span className="text-xs text-slate-500">Station</span>
                    <select
                      value={auth.stationId}
                      onChange={(e) => updateAuth({ stationId: e.target.value })}
                      className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-300"
                    >
                      {stations.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="grid gap-1 text-sm">
                    <span className="text-xs text-slate-500">User</span>
                    <select
                      value={auth.userId}
                      onChange={(e) => updateAuth({ userId: e.target.value })}
                      className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-slate-300"
                    >
                      {metaUsers.map((u) => (
                        <option key={u.user_id} value={u.user_id}>
                          {u.user_id}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="min-w-0">
                  <div className="text-xs text-slate-500">Rollen</div>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {splitRoles(auth.rolesCsv).map((r) => (
                      <span
                        key={r}
                        className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-700"
                      >
                        {r}
                      </span>
                    ))}
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Rollen werden aus dem User abgeleitet (kein Freitext). {metaError ? `(${metaError})` : ""}
                  </div>
                </div>
              </div>
            </div>


            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
  <div className="rounded-2xl border border-slate-200 bg-white p-4">
    <div className="text-xs text-slate-500">Fälle gesamt</div>
    <div className="mt-1 text-2xl font-semibold">{cases.length}</div>
  </div>

  <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
    <div className="text-xs text-red-700">Critical</div>
    <div className="mt-1 text-2xl font-semibold text-red-800">
      {cases.filter(c => (c.critical_count ?? 0) > 0).length}
    </div>
  </div>

  <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
    <div className="text-xs text-amber-800">Warn</div>
    <div className="mt-1 text-2xl font-semibold text-amber-900">
      {cases.filter(c => (c.warn_count ?? 0) > 0).length}
    </div>
  </div>
</div>


            {/* Fälle */}
            <div className="space-y-2">
              {cases.map((c) => (
                <button
                  key={c.case_id}
                  onClick={() => setSelectedCaseId(c.case_id)}
                  className={[
                    "w-full rounded-2xl border bg-white p-4 text-left shadow-sm transition",
                    "border-slate-200 hover:bg-slate-50",
                    selectedCaseId === c.case_id ? "ring-2 ring-slate-300" : "",
                    c.acked_at ? "opacity-70" : "",
                  ].join(" ")}
                  title={c.acked_at ? `Quittiert: ${c.acked_at}` : "Nicht quittiert"}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold">{c.case_id}</div>
                      <div className="mt-1 text-xs text-slate-600">
                        Status: <span className="font-medium">{c.severity}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 text-xs">
                      {(c.critical_count ?? 0) > 0 && (
                        <span className="rounded-full bg-red-50 px-2 py-1 text-red-700 ring-1 ring-red-100">
                          ‼ {c.critical_count}
                        </span>
                      )}
                      {(c.warn_count ?? 0) > 0 && (
                        <span className="rounded-full bg-amber-50 px-2 py-1 text-amber-800 ring-1 ring-amber-100">
                          ⚠ {c.warn_count}
                        </span>
                      )}
                      {c.acked_at && (
                        <span className="rounded-full bg-emerald-50 px-2 py-1 text-emerald-800 ring-1 ring-emerald-100">
                          ✓ quittiert
                        </span>
                      )}
                    </div>
                  </div>

                  {c.top_alert && (
                    <div className="mt-3 text-sm text-slate-700">
                      <span className="font-medium">Hinweis:</span> {c.top_alert}
                    </div>
                  )}
                </button>
              ))}

              {cases.length === 0 && !error && (
                <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
                  Keine Fälle für diese Station.
                </div>
              )}
            </div>
          </section>

          {/* RIGHT */}
          <aside className="lg:sticky lg:top-6">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              {!selectedCaseId && <div className="text-sm text-slate-700">Fall auswählen, um Details zu sehen.</div>}

              {selectedCaseId && detailLoading && <div className="text-sm text-slate-700">Lade Details…</div>}

              {selectedCaseId && detailError && (
                <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                  Fehler: {detailError}
                </div>
              )}

              {detail && !detailLoading && !detailError && (
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold">{detail.case_id}</div>
                      <div className="mt-1 text-xs text-slate-600">
                        Station: <span className="font-medium">{detail.station_id}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => setSelectedCaseId(null)}
                      className="rounded-lg border border-slate-200 bg-white px-2 py-1 text-sm hover:bg-slate-50"
                      aria-label="Close details"
                    >
                      ✕
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">Eintritt</div>
                      <div className="mt-1 font-medium">{detail.admission_date}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">BFS vollständig</div>
                      <div className="mt-1 font-medium">{detail.bfs_complete ? "Ja" : "Nein"}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">HONOS</div>
                      <div className="mt-1 font-medium">{detail.honos ?? "—"}</div>
                    </div>
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">BSCL</div>
                      <div className="mt-1 font-medium">{detail.bscl ?? "—"}</div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm">
                      <span className="text-slate-600">Quittiert:</span>{" "}
                      <span className="font-medium">{detail.acked_at ? `Ja (${detail.acked_at})` : "Nein"}</span>
                    </div>

                    {!detail.acked_at && (
                      <button
                        disabled={!canAck}
                        onClick={async () => {
                          if (!canAck) return;
                          const res = await ackCase(detail.case_id, auth);
                          setDetail({ ...detail, acked_at: res.acked_at });
                          setCases((prev) =>
                            prev.map((c) =>
                              c.case_id === detail.case_id ? { ...c, acked_at: res.acked_at } : c
                            )
                          );
                          setToast((t) => (t && t.caseId === detail.case_id ? null : t));
                        }}
                        className={[
                          "rounded-xl px-3 py-2 text-sm font-medium",
                          canAck
                            ? "border border-slate-200 bg-slate-900 text-white hover:bg-slate-800"
                            : "cursor-not-allowed border border-slate-200 bg-slate-200 text-slate-500",
                        ].join(" ")}
                        title={canAck ? "Fall quittieren" : "Keine Berechtigung (ACK_ALERT fehlt)"}
                      >
                        Fall quittieren
                      </button>
                    )}
                  </div>

                  <div>
                    <div className="mb-2 text-sm font-semibold">Alerts</div>

                    {detail.alerts.length === 0 ? (
                      <div className="text-sm text-slate-600">Keine Alerts.</div>
                    ) : (
                      <ul className="space-y-2">
                        {detail.alerts.map((a) => (
                          <li key={a.rule_id} className="rounded-xl border border-slate-200 p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="flex items-center gap-2 text-sm">
                                  <span className={`rounded-full px-2 py-1 text-xs ${severityPill(a.severity as Severity)}`}>
                                    {a.severity}
                                  </span>
                                  <span className="text-slate-700">{a.message}</span>
                                </div>
                                {a.explanation && (
                                  <div className="mt-2 text-xs text-slate-500">{a.explanation}</div>
                                )}
                              </div>

                              <button
                                disabled={!canAck}
                                onClick={async () => {
                                  if (!canAck) return;
                                  await ackRule(detail.case_id, a.rule_id, auth);

                                  const [newList, newDetail] = await Promise.all([
                                    fetchCases(auth),
                                    fetchCaseDetail(detail.case_id, auth),
                                  ]);
                                  setCases(newList);
                                  setDetail(newDetail);

                                  setToast((t) => {
                                    if (!t || t.caseId !== detail.case_id) return t;
                                    const updated = newList.find((x) => x.case_id === detail.case_id);
                                    if (!updated || (updated.critical_count ?? 0) === 0) return null;
                                    return t;
                                  });
                                }}
                                className={[
                                  "rounded-lg px-2.5 py-1.5 text-xs",
                                  canAck
                                    ? "border border-slate-200 bg-white hover:bg-slate-50"
                                    : "cursor-not-allowed border border-slate-200 bg-slate-100 text-slate-400",
                                ].join(" ")}
                                title={canAck ? "Alert quittieren (bis morgen ausgeblendet)" : "Keine Berechtigung"}
                              >
                                Quittieren
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </div>
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
                    await ackCase(toast.caseId, auth);
                    setToast(null);
                    const data = await fetchCases(auth);
                    setCases(data);
                  }
                : undefined
            }
            onClose={() => setToast(null)}
          />
        )}
      </main>
    </div>
  );
}
