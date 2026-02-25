/**
 * Datei: frontend/src/AdminPanel.tsx
 *
 * Admin-Panel mit Tabs für:
 * - CSV Import (NEU)
 * - Schiebe-Gründe (NEU)
 * - Benutzer
 * - Rollen
 * - Regeln
 * - Audit-Log
 */

import { useEffect, useMemo, useState } from "react";

type AuthState = { stationId: string; userId: string };
type MetaMe = { user_id: string; station_id: string; roles: string[]; permissions: string[]; break_glass: boolean };
type Props = { auth: AuthState; authHeaders: (auth: AuthState) => HeadersInit; me: MetaMe | null };

type AdminUser = { user_id: string; display_name: string | null; is_active: boolean; created_at: string; roles: { role_id: string; station_id: string }[] };
type AdminRole = { role_id: string; description: string | null; permissions: string[]; is_system: boolean };
type AdminPermission = { perm_id: string; description: string | null; is_system: boolean };
type RuleDef = { rule_id: string; display_name: string | null; message: string; explanation: string; category: string; severity: "OK" | "WARN" | "CRITICAL"; metric: string; operator: string; value_json: string; enabled: boolean; is_system: boolean; updated_at: string | null; updated_by: string | null };
type AuditEvent = { event_id: string; ts: string; actor_user_id: string | null; actor_station_id: string | null; action: string; target_type: string | null; target_id: string | null; success: boolean; message: string | null; details: string | null };
type ShiftReasonAdmin = { id: number; code: string; label: string; description: string | null; is_active: boolean; sort_order: number };
type NotificationRuleAdmin = { id: number; name: string; email: string; station_id: string | null; min_severity: string; category: string | null; delay_minutes: number; is_active: boolean; created_at: string | null; created_by: string | null };

async function apiJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) { const text = await res.text().catch(() => ""); throw new Error(text || `HTTP ${res.status}`); }
  return (await res.json()) as T;
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff", marginTop: 12 }}>
      <h3 style={{ marginTop: 0, marginBottom: 12, fontSize: "1rem", color: "#1e293b" }}>{title}</h3>
      {children}
    </section>
  );
}

export function AdminPanel({ auth, authHeaders, me }: Props) {
  const canRead = useMemo(() => new Set(me?.permissions ?? []).has("admin:read"), [me]);
  const canWrite = useMemo(() => new Set(me?.permissions ?? []).has("admin:write"), [me]);

  const [tab, setTab] = useState<"csv" | "shift_reasons" | "notifications" | "users" | "roles" | "rules" | "audit">("csv");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [permissions, setPermissions] = useState<AdminPermission[]>([]);
  const [rules, setRules] = useState<RuleDef[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [shiftReasons, setShiftReasons] = useState<ShiftReasonAdmin[]>([]);
  const [notifications, setNotifications] = useState<NotificationRuleAdmin[]>([]);

  async function refreshAll() {
    setError(null);
    if (!canRead) return;
    try { const u = await apiJson<{ users: AdminUser[] }>("/api/admin/users", { method: "GET", headers: authHeaders(auth) }); setUsers(u.users); } catch {}
    try { const r = await apiJson<{ roles: AdminRole[] }>("/api/admin/roles", { method: "GET", headers: authHeaders(auth) }); setRoles(r.roles); } catch {}
    try { const p = await apiJson<{ permissions: AdminPermission[] }>("/api/admin/permissions", { method: "GET", headers: authHeaders(auth) }); setPermissions(p.permissions); } catch {}
    try { const rr = await apiJson<{ rules: RuleDef[] }>("/api/admin/rules", { method: "GET", headers: authHeaders(auth) }); setRules(rr.rules); } catch {}
    try { const a = await apiJson<{ events: AuditEvent[] }>("/api/admin/audit?limit=200", { method: "GET", headers: authHeaders(auth) }); setAudit(a.events); } catch {}
    try { const sr = await apiJson<{ reasons: ShiftReasonAdmin[] }>("/api/admin/shift_reasons", { method: "GET", headers: authHeaders(auth) }); setShiftReasons(sr.reasons); } catch {}
    try { const nr = await apiJson<{ rules: NotificationRuleAdmin[] }>("/api/admin/notifications", { method: "GET", headers: authHeaders(auth) }); setNotifications(nr.rules); } catch {}
  }

  useEffect(() => { refreshAll(); }, [auth.stationId, auth.userId]);

  const tabStyle = (t: string) => ({
    padding: "8px 16px", borderRadius: 8, border: "1px solid #e2e8f0", cursor: "pointer",
    background: tab === t ? "#3b82f6" : "#fff", color: tab === t ? "#fff" : "#333",
    fontWeight: tab === t ? 700 : 400, fontSize: 13,
  });

  return (
    <div style={{ minHeight: 400 }}>
      {error && <div style={{ padding: "8px 12px", color: "#b42318", background: "#fef2f2", borderRadius: 8, marginBottom: 8, fontSize: 13 }}>{error}</div>}
      {success && <div style={{ padding: "8px 12px", color: "#15803d", background: "#f0fdf4", borderRadius: 8, marginBottom: 8, fontSize: 13 }}>{success}</div>}

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
        <button style={tabStyle("csv")} onClick={() => setTab("csv")}>📥 CSV Import</button>
        <button style={tabStyle("shift_reasons")} onClick={() => setTab("shift_reasons")}>🔄 Schiebe-Gründe</button>
        <button style={tabStyle("notifications")} onClick={() => setTab("notifications")}>📧 Benachrichtigungen</button>
        <button style={tabStyle("users")} onClick={() => setTab("users")}>👤 Benutzer</button>
        <button style={tabStyle("roles")} onClick={() => setTab("roles")}>🔑 Rollen</button>
        <button style={tabStyle("rules")} onClick={() => setTab("rules")}>📏 Regeln</button>
        <button style={tabStyle("audit")} onClick={() => setTab("audit")}>📋 Audit</button>
      </div>

      {/* CSV IMPORT TAB */}
      {tab === "csv" && <CSVImportTab auth={auth} authHeaders={authHeaders} canWrite={canWrite} onError={setError} onSuccess={(msg) => { setSuccess(msg); setTimeout(() => setSuccess(null), 5000); }} />}

      {/* SHIFT REASONS TAB */}
      {tab === "shift_reasons" && <ShiftReasonsTab reasons={shiftReasons} auth={auth} authHeaders={authHeaders} canWrite={canWrite} onRefresh={refreshAll} onError={setError} />}

      {/* NOTIFICATIONS TAB */}
      {tab === "notifications" && <NotificationsTab rules={notifications} auth={auth} authHeaders={authHeaders} canWrite={canWrite} onRefresh={refreshAll} onError={setError} />}

      {/* USERS TAB */}
      {tab === "users" && <UsersTab users={users} roles={roles} auth={auth} authHeaders={authHeaders} canWrite={canWrite} onRefresh={refreshAll} onError={setError} />}

      {/* ROLES TAB */}
      {tab === "roles" && <RolesTab roles={roles} permissions={permissions} auth={auth} authHeaders={authHeaders} canWrite={canWrite} onRefresh={refreshAll} onError={setError} />}

      {/* RULES TAB */}
      {tab === "rules" && <RulesTab rules={rules} auth={auth} authHeaders={authHeaders} canWrite={canWrite} onRefresh={refreshAll} onError={setError} />}

      {/* AUDIT TAB */}
      {tab === "audit" && (
        <SectionCard title="Audit-Log">
          <div style={{ fontSize: 12, opacity: 0.7, marginBottom: 8 }}>Letzte Aktionen. Erfordert <code>audit:read</code>.</div>
          <div style={{ maxHeight: 500, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  {["Zeitpunkt", "Aktion", "Akteur", "Ziel", "OK"].map(h => (
                    <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0", padding: "6px 4px", color: "#64748b" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.event_id}>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2", whiteSpace: "nowrap" }}>{e.ts?.substring(0, 19)}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}><code>{e.action}</code></td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{e.actor_user_id ?? "—"}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{e.target_type ?? ""} {e.target_id ?? ""}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{e.success ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}

// ============================================================
// CSV Import Tab
// ============================================================
function CSVImportTab({ auth, authHeaders, canWrite, onError, onSuccess }: {
  auth: AuthState; authHeaders: (a: AuthState) => HeadersInit; canWrite: boolean;
  onError: (msg: string) => void; onSuccess: (msg: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [stationFilter, setStationFilter] = useState("");
  const [overwrite, setOverwrite] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [caseCount, setCaseCount] = useState<any>(null);

  useEffect(() => {
    fetch("/api/admin/cases/count", { headers: authHeaders(auth) })
      .then(r => r.json()).then(setCaseCount).catch(() => {});
  }, [result]);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (stationFilter.trim()) formData.append("station_id", stationFilter.trim());
      formData.append("overwrite", String(overwrite));

      const h = authHeaders(auth) as Record<string, string>;
      delete h["Content-Type"]; // Let browser set multipart boundary

      const res = await fetch("/api/admin/csv/upload", {
        method: "POST", headers: h, body: formData,
      });
      const data = await res.json();
      setResult(data);
      if (data.success) onSuccess(`Import erfolgreich: ${data.imported_rows} Fälle importiert`);
      else onError(`Import teilweise fehlgeschlagen: ${data.failed_rows} Fehler`);
    } catch (e: any) {
      onError(e?.message ?? String(e));
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteAll() {
    if (!window.confirm("ACHTUNG: Alle importierten Fälle werden gelöscht!\n\nDiese Aktion kann nicht rückgängig gemacht werden.\n\nFortfahren?")) return;
    try {
      const h = authHeaders(auth) as Record<string, string>;
      await fetch("/api/admin/cases/all", { method: "DELETE", headers: h });
      onSuccess("Alle Fälle gelöscht");
      setResult(null);
      setCaseCount(null);
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  return (
    <SectionCard title="CSV / Excel Import">
      <div style={{ display: "grid", gap: 16 }}>
        {/* Case count */}
        {caseCount && (
          <div style={{ padding: 12, background: "#f8fafc", borderRadius: 8, border: "1px solid #e2e8f0" }}>
            <strong>Aktuell in DB:</strong> {caseCount.total} Fälle
            {caseCount.by_station && Object.keys(caseCount.by_station).length > 0 && (
              <span style={{ marginLeft: 12, color: "#64748b" }}>
                ({Object.entries(caseCount.by_station).map(([k, v]) => `${k}: ${v}`).join(", ")})
              </span>
            )}
          </div>
        )}

        {/* Upload form */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4, color: "#334155" }}>Datei (.csv / .xlsx)</label>
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] ?? null)} style={{ padding: 8, border: "1px solid #ccc", borderRadius: 8, width: "100%", boxSizing: "border-box" }} />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 700, marginBottom: 4, color: "#334155" }}>Station (optional, überschreibt Spalte)</label>
            <input placeholder="z.B. A1" value={stationFilter} onChange={(e) => setStationFilter(e.target.value)} style={{ padding: 8, border: "1px solid #ccc", borderRadius: 8, width: "100%", boxSizing: "border-box" }} />
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
            Bestehende Fälle überschreiben
          </label>
          <button disabled={!canWrite || !file || uploading} onClick={handleUpload} style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid #3b82f6", background: "#3b82f6", color: "#fff", fontWeight: 700, cursor: canWrite && file ? "pointer" : "not-allowed", opacity: canWrite && file ? 1 : 0.5 }}>
            {uploading ? "Importiert..." : "📥 Importieren"}
          </button>
          <a href="/api/admin/csv/sample" download="sample_cases.csv" style={{ fontSize: 13, color: "#3b82f6" }}>
            Beispiel-CSV herunterladen
          </a>
        </div>

        {/* Result */}
        {result && (
          <div style={{ padding: 12, borderRadius: 8, border: "1px solid #e2e8f0", background: result.success ? "#f0fdf4" : "#fef2f2" }}>
            <div><strong>Ergebnis:</strong> {result.success ? "✓ Erfolgreich" : "⚠ Fehler"}</div>
            <div style={{ fontSize: 13, marginTop: 4 }}>
              Gesamt: {result.total_rows} · Importiert: {result.imported_rows} · Übersprungen: {result.skipped_rows ?? 0} · Fehler: {result.failed_rows}
            </div>
            {result.errors?.length > 0 && (
              <details style={{ marginTop: 8 }}>
                <summary style={{ cursor: "pointer", fontSize: 13, color: "#b42318" }}>Fehlerdetails ({result.errors.length})</summary>
                <div style={{ maxHeight: 200, overflow: "auto", fontSize: 12, marginTop: 4 }}>
                  {result.errors.map((e: any, i: number) => (
                    <div key={i} style={{ padding: "4px 0", borderBottom: "1px solid #f2f2f2" }}>
                      Zeile {e.row}: {e.error} {e.case_id ? `(${e.case_id})` : ""}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {/* Danger zone */}
        <div style={{ borderTop: "1px solid #fecaca", paddingTop: 12 }}>
          <button onClick={handleDeleteAll} disabled={!canWrite} style={{ padding: "6px 12px", borderRadius: 8, border: "1px solid #fecaca", background: "#fff1f2", color: "#b42318", fontWeight: 700, cursor: canWrite ? "pointer" : "not-allowed", fontSize: 12 }}>
            ⚠ Alle Fälle löschen
          </button>
        </div>
      </div>
    </SectionCard>
  );
}

// ============================================================
// ShiftReasons Tab
// ============================================================
function ShiftReasonsTab({ reasons, auth, authHeaders, canWrite, onRefresh, onError }: {
  reasons: ShiftReasonAdmin[]; auth: AuthState; authHeaders: (a: AuthState) => HeadersInit;
  canWrite: boolean; onRefresh: () => void; onError: (msg: string) => void;
}) {
  const [newCode, setNewCode] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [newDesc, setNewDesc] = useState("");

  async function addReason() {
    if (!newCode.trim() || !newLabel.trim()) return;
    try {
      await apiJson("/api/admin/shift_reasons", {
        method: "POST", headers: authHeaders(auth),
        body: JSON.stringify({ code: newCode.trim(), label: newLabel.trim(), description: newDesc.trim() || null, sort_order: reasons.length }),
      });
      setNewCode(""); setNewLabel(""); setNewDesc("");
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function toggleActive(id: number, active: boolean) {
    try {
      await apiJson(`/api/admin/shift_reasons/${id}`, {
        method: "PUT", headers: authHeaders(auth),
        body: JSON.stringify({ is_active: !active }),
      });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function deleteReason(id: number) {
    if (!window.confirm("Schiebe-Grund löschen?")) return;
    try {
      await apiJson(`/api/admin/shift_reasons/${id}`, { method: "DELETE", headers: authHeaders(auth) });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  return (
    <SectionCard title="Schiebe-Gründe verwalten">
      <div style={{ fontSize: 13, color: "#64748b", marginBottom: 12 }}>
        Hier können Sie die Gründe konfigurieren, die beim "Nochmal erinnern" eines Alerts zur Auswahl stehen.
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 16 }}>
        <thead>
          <tr>
            {["Code", "Label", "Beschreibung", "Aktiv", "Aktionen"].map(h => (
              <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0", padding: "8px 6px", color: "#64748b" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {reasons.map((r) => (
            <tr key={r.id}>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}><code>{r.code}</code></td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{r.label}</td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2", color: "#64748b" }}>{r.description ?? "—"}</td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                <button onClick={() => toggleActive(r.id, r.is_active)} disabled={!canWrite} style={{ background: "none", border: "none", cursor: canWrite ? "pointer" : "default", fontSize: 14 }}>
                  {r.is_active ? "✅" : "❌"}
                </button>
              </td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                <button onClick={() => deleteReason(r.id)} disabled={!canWrite} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #fecaca", background: "#fff1f2", color: "#b42318", fontSize: 11, cursor: canWrite ? "pointer" : "not-allowed" }}>Löschen</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {canWrite && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Code</label>
            <input value={newCode} onChange={(e) => setNewCode(e.target.value)} placeholder="d" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 60 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Label</label>
            <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="Neuer Grund" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 180 }} />
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Beschreibung</label>
            <input value={newDesc} onChange={(e) => setNewDesc(e.target.value)} placeholder="Optional" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 200 }} />
          </div>
          <button onClick={addReason} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #3b82f6", background: "#3b82f6", color: "#fff", fontWeight: 700, cursor: "pointer" }}>+ Hinzufügen</button>
        </div>
      )}
    </SectionCard>
  );
}

// ============================================================
// Users Tab
// ============================================================
function UsersTab({ users, roles, auth, authHeaders, canWrite, onRefresh, onError }: {
  users: AdminUser[]; roles: AdminRole[]; auth: AuthState; authHeaders: (a: AuthState) => HeadersInit;
  canWrite: boolean; onRefresh: () => void; onError: (msg: string) => void;
}) {
  const [createUserId, setCreateUserId] = useState("");
  const [createDisplayName, setCreateDisplayName] = useState("");
  const [createInitialRole, setCreateInitialRole] = useState("viewer");

  async function createUser() {
    if (!createUserId.trim()) return;
    try {
      await apiJson("/api/admin/users", {
        method: "POST", headers: authHeaders(auth),
        body: JSON.stringify({ user_id: createUserId.trim(), display_name: createDisplayName.trim() || null, is_active: true, roles: createInitialRole ? [{ role_id: createInitialRole, station_id: "*" }] : [] }),
      });
      setCreateUserId(""); setCreateDisplayName("");
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function deleteUser(uid: string) {
    if (!window.confirm(`Benutzer "${uid}" löschen?`)) return;
    try {
      await apiJson(`/api/admin/users/${uid}`, { method: "DELETE", headers: authHeaders(auth) });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  return (
    <SectionCard title="Benutzerverwaltung">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 16 }}>
        <thead>
          <tr>
            {["User-ID", "Name", "Aktiv", "Rollen", "Aktionen"].map(h => (
              <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0", padding: "8px 6px", color: "#64748b" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id}>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2", fontWeight: 700 }}>{u.user_id}</td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{u.display_name ?? "—"}</td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{u.is_active ? "✅" : "❌"}</td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2", fontSize: 12 }}>
                {u.roles.map(r => `${r.role_id}@${r.station_id}`).join(", ") || "—"}
              </td>
              <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                <button onClick={() => deleteUser(u.user_id)} disabled={!canWrite || u.user_id === auth.userId} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #fecaca", background: "#fff1f2", color: "#b42318", fontSize: 11, cursor: canWrite ? "pointer" : "not-allowed" }}>Löschen</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {canWrite && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div><label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>User-ID</label><input value={createUserId} onChange={(e) => setCreateUserId(e.target.value)} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 120 }} /></div>
          <div><label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Name</label><input value={createDisplayName} onChange={(e) => setCreateDisplayName(e.target.value)} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 150 }} /></div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Rolle</label>
            <select value={createInitialRole} onChange={(e) => setCreateInitialRole(e.target.value)} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6 }}>
              {roles.map(r => <option key={r.role_id} value={r.role_id}>{r.role_id}</option>)}
            </select>
          </div>
          <button onClick={createUser} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #3b82f6", background: "#3b82f6", color: "#fff", fontWeight: 700, cursor: "pointer" }}>+ Erstellen</button>
        </div>
      )}
    </SectionCard>
  );
}

// ============================================================
// Roles Tab
// ============================================================
function RolesTab({ roles, permissions, auth, authHeaders, canWrite, onRefresh, onError }: {
  roles: AdminRole[]; permissions: AdminPermission[]; auth: AuthState; authHeaders: (a: AuthState) => HeadersInit;
  canWrite: boolean; onRefresh: () => void; onError: (msg: string) => void;
}) {
  return (
    <SectionCard title="Rollen & Berechtigungen">
      <div style={{ display: "grid", gap: 10 }}>
        {roles.map(r => (
          <div key={r.role_id} style={{ padding: 10, border: "1px solid #e2e8f0", borderRadius: 8, background: "#f8fafc" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{r.role_id}</strong>
                {r.is_system && <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 8 }}>System</span>}
              </div>
              <div style={{ fontSize: 12, color: "#64748b" }}>{r.description}</div>
            </div>
            <div style={{ fontSize: 12, marginTop: 4, color: "#475569" }}>
              Rechte: {r.permissions.join(", ") || "—"}
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ============================================================
// Rules Tab
// ============================================================

const CATEGORY_LABELS: Record<string, { label: string; icon: string; color: string; bg: string; border: string }> = {
  completeness: { label: "Dokumentation", icon: "📋", color: "#1d4ed8", bg: "#dbeafe", border: "#93c5fd" },
  medical: { label: "Klinisch", icon: "🩺", color: "#be185d", bg: "#fce7f3", border: "#f9a8d4" },
};
const SEV_COLORS: Record<string, { color: string; bg: string }> = {
  CRITICAL: { color: "#991b1b", bg: "#fecaca" },
  WARN: { color: "#92400e", bg: "#fef3c7" },
  OK: { color: "#166534", bg: "#dcfce7" },
};
const OPERATOR_LABELS: Record<string, string> = {
  is_true: "ist wahr", is_false: "ist falsch", is_null: "fehlt",
  ">": "grösser als", ">=": "grösser/gleich",
};

function RulesTab({ rules, auth, authHeaders, canWrite, onRefresh, onError }: {
  rules: RuleDef[]; auth: AuthState; authHeaders: (a: AuthState) => HeadersInit;
  canWrite: boolean; onRefresh: () => void; onError: (msg: string) => void;
}) {
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [ruleEdit, setRuleEdit] = useState<Partial<RuleDef> & { value?: any } | null>(null);
  const [ruleValueEdit, setRuleValueEdit] = useState("");
  const [rulesView, setRulesView] = useState<"catalog" | "editor">("catalog");

  const selectedRule = rules.find(r => r.rule_id === selectedRuleId) ?? null;

  // Group rules by category
  const groupedRules = useMemo(() => {
    const groups: Record<string, RuleDef[]> = {};
    for (const r of rules) {
      const cat = r.category || "medical";
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(r);
    }
    return groups;
  }, [rules]);

  useEffect(() => {
    if (!selectedRule) { setRuleEdit(null); return; }
    let val: any = null;
    try { val = JSON.parse(selectedRule.value_json); } catch {}
    setRuleEdit({ ...selectedRule, value: val });
    setRuleValueEdit(selectedRule.value_json ?? "");
  }, [selectedRuleId, rules]);

  async function saveRule() {
    if (!ruleEdit?.rule_id) return;
    let parsed: any;
    try { parsed = JSON.parse(ruleValueEdit); } catch { onError("Ungültiger JSON-Wert"); return; }
    try {
      await apiJson(`/api/admin/rules/${encodeURIComponent(ruleEdit.rule_id)}`, {
        method: "PUT", headers: authHeaders(auth),
        body: JSON.stringify({ rule_id: ruleEdit.rule_id, display_name: ruleEdit.display_name ?? null, message: ruleEdit.message ?? "", explanation: ruleEdit.explanation ?? "", category: ruleEdit.category ?? "medical", severity: ruleEdit.severity ?? "WARN", metric: ruleEdit.metric ?? "", operator: ruleEdit.operator ?? "is_true", value: parsed, enabled: ruleEdit.enabled ?? true }),
      });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  function openInEditor(ruleId: string) {
    setSelectedRuleId(ruleId);
    setRulesView("editor");
  }

  const inputStyle: React.CSSProperties = { padding: "8px 10px", border: "1px solid #d1d5db", borderRadius: 8, width: "100%", boxSizing: "border-box" as const, fontSize: 13 };
  const labelStyle: React.CSSProperties = { fontSize: 12, fontWeight: 600, display: "block", marginBottom: 4, color: "#374151" };

  return (
    <div style={{ marginTop: 12 }}>
      {/* View toggle */}
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        {([
          { key: "catalog" as const, label: "📖 Regelkatalog", desc: "Übersicht aller Regeln" },
          { key: "editor" as const, label: "✏️ Regel-Editor", desc: "Regeln bearbeiten" },
        ]).map(v => (
          <button
            key={v.key}
            onClick={() => setRulesView(v.key)}
            style={{
              padding: "8px 16px", fontSize: 13, fontWeight: rulesView === v.key ? 700 : 500,
              borderRadius: 8, cursor: "pointer", transition: "all 0.15s",
              background: rulesView === v.key ? "#1e40af" : "#f1f5f9",
              color: rulesView === v.key ? "#fff" : "#475569",
              border: rulesView === v.key ? "1px solid #1e40af" : "1px solid #e2e8f0",
            }}
          >
            {v.label}
          </button>
        ))}
        <span style={{ fontSize: 12, color: "#94a3b8", alignSelf: "center", marginLeft: 8 }}>
          {rules.length} Regeln ({rules.filter(r => r.enabled).length} aktiv)
        </span>
      </div>

      {/* ═══ CATALOG VIEW ═══ */}
      {rulesView === "catalog" && (
        <div>
          {Object.entries(groupedRules).map(([cat, catRules]) => {
            const catInfo = CATEGORY_LABELS[cat] ?? { label: cat, icon: "📌", color: "#475569", bg: "#f1f5f9", border: "#e2e8f0" };
            const activeCount = catRules.filter(r => r.enabled).length;
            return (
              <div key={cat} style={{ marginBottom: 20 }}>
                {/* Category header */}
                <div style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "10px 16px",
                  background: catInfo.bg, borderRadius: "10px 10px 0 0", border: `1px solid ${catInfo.border}`, borderBottom: "none",
                }}>
                  <span style={{ fontSize: 18 }}>{catInfo.icon}</span>
                  <span style={{ fontWeight: 700, fontSize: 15, color: catInfo.color }}>{catInfo.label}</span>
                  <span style={{ fontSize: 12, color: "#6b7280" }}>({activeCount}/{catRules.length} aktiv)</span>
                </div>
                {/* Rules table */}
                <table style={{ width: "100%", borderCollapse: "collapse", border: `1px solid ${catInfo.border}`, borderRadius: "0 0 10px 10px", overflow: "hidden" }}>
                  <thead>
                    <tr style={{ background: "#f9fafb", fontSize: 12, color: "#6b7280" }}>
                      <th style={{ padding: "8px 12px", textAlign: "left", width: 50 }}>Aktiv</th>
                      <th style={{ padding: "8px 12px", textAlign: "left" }}>Regel</th>
                      <th style={{ padding: "8px 12px", textAlign: "left", width: 80 }}>Stufe</th>
                      <th style={{ padding: "8px 12px", textAlign: "left", width: 200 }}>Datenfeld</th>
                      <th style={{ padding: "8px 12px", textAlign: "left" }}>Erklärung</th>
                      {canWrite && <th style={{ padding: "8px 12px", width: 60 }}></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {catRules.map(r => {
                      const sev = SEV_COLORS[r.severity] ?? SEV_COLORS.OK;
                      const opLabel = OPERATOR_LABELS[r.operator] ?? r.operator;
                      return (
                        <tr key={r.rule_id} style={{ borderTop: "1px solid #f3f4f6", opacity: r.enabled ? 1 : 0.5 }}>
                          <td style={{ padding: "8px 12px", textAlign: "center" }}>
                            {canWrite ? (
                              <button
                                onClick={async () => {
                                  try {
                                    let val: any = null;
                                    try { val = JSON.parse(r.value_json); } catch {}
                                    await apiJson(`/api/admin/rules/${encodeURIComponent(r.rule_id)}`, {
                                      method: "PUT", headers: authHeaders(auth),
                                      body: JSON.stringify({ rule_id: r.rule_id, display_name: r.display_name, message: r.message, explanation: r.explanation, category: r.category, severity: r.severity, metric: r.metric, operator: r.operator, value: val, enabled: !r.enabled }),
                                    });
                                    onRefresh();
                                  } catch (e: any) { onError(e?.message ?? String(e)); }
                                }}
                                title={r.enabled ? "Klicken zum Deaktivieren" : "Klicken zum Aktivieren"}
                                style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, padding: 2 }}
                              >
                                {r.enabled ? "🟢" : "🔴"}
                              </button>
                            ) : (
                              <span style={{ color: r.enabled ? "#16a34a" : "#dc2626", fontSize: 16 }}>{r.enabled ? "●" : "○"}</span>
                            )}
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{r.display_name ?? r.message}</div>
                            <div style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>{r.rule_id}</div>
                          </td>
                          <td style={{ padding: "8px 12px" }}>
                            <span style={{ padding: "2px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700, background: sev.bg, color: sev.color }}>
                              {r.severity}
                            </span>
                          </td>
                          <td style={{ padding: "8px 12px", fontSize: 12 }}>
                            <code style={{ fontSize: 12, background: "#f1f5f9", padding: "3px 8px", borderRadius: 4, fontFamily: "monospace", display: "inline-block" }}>{r.metric}</code>
                            <div style={{ fontSize: 11, color: "#6b7280", marginTop: 2 }}>{opLabel} <code style={{ fontSize: 10 }}>{r.value_json}</code></div>
                          </td>
                          <td style={{ padding: "8px 12px", fontSize: 12, color: "#64748b", maxWidth: 300 }}>
                            {r.explanation?.substring(0, 100)}{r.explanation && r.explanation.length > 100 ? "…" : ""}
                          </td>
                          {canWrite && (
                            <td style={{ padding: "8px 12px", textAlign: "center" }}>
                              <button
                                onClick={() => openInEditor(r.rule_id)}
                                style={{ padding: "4px 10px", fontSize: 11, borderRadius: 6, border: "1px solid #d1d5db", background: "#fff", cursor: "pointer", color: "#475569" }}
                              >
                                ✏️
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>
      )}

      {/* ═══ EDITOR VIEW ═══ */}
      {rulesView === "editor" && (
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16 }}>
          {/* Left: Rule list */}
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, background: "#fff", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0", fontWeight: 700, fontSize: 14, color: "#1e293b" }}>
              Regeln auswählen
            </div>
            <div style={{ maxHeight: 560, overflow: "auto", padding: 8 }}>
              {Object.entries(groupedRules).map(([cat, catRules]) => {
                const catInfo = CATEGORY_LABELS[cat] ?? { label: cat, icon: "📌", color: "#475569", bg: "#f1f5f9", border: "#e2e8f0" };
                return (
                  <div key={cat}>
                    <div style={{ padding: "6px 8px", fontSize: 11, fontWeight: 700, color: catInfo.color, textTransform: "uppercase" as const, letterSpacing: 0.5, display: "flex", alignItems: "center", gap: 4 }}>
                      <span>{catInfo.icon}</span>{catInfo.label}
                    </div>
                    {catRules.map(r => {
                      const isSelected = selectedRuleId === r.rule_id;
                      const sev = SEV_COLORS[r.severity] ?? SEV_COLORS.OK;
                      return (
                        <div
                          key={r.rule_id}
                          onClick={() => setSelectedRuleId(r.rule_id)}
                          style={{
                            padding: "8px 10px", borderRadius: 8, cursor: "pointer", marginBottom: 4,
                            background: isSelected ? "#eef2ff" : "#fff",
                            border: isSelected ? "1px solid #818cf8" : "1px solid transparent",
                            transition: "all 0.1s",
                          }}
                        >
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: 13, fontWeight: isSelected ? 700 : 500, color: "#1e293b" }}>
                              {r.display_name ?? r.message}
                            </span>
                            <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
                              <span style={{ padding: "1px 6px", borderRadius: 999, fontSize: 10, fontWeight: 700, background: sev.bg, color: sev.color }}>{r.severity}</span>
                              <span style={{ fontSize: 11, color: r.enabled ? "#16a34a" : "#dc2626" }}>{r.enabled ? "●" : "○"}</span>
                            </span>
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>{r.rule_id}</div>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right: Editor */}
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 12, background: "#fff", overflow: "hidden" }}>
            <div style={{ padding: "12px 16px", background: "#f8fafc", borderBottom: "1px solid #e2e8f0", fontWeight: 700, fontSize: 14, color: "#1e293b" }}>
              {ruleEdit ? `Regel bearbeiten: ${ruleEdit.display_name ?? ruleEdit.message ?? ruleEdit.rule_id}` : "Regel-Editor"}
            </div>
            <div style={{ padding: 16 }}>
              {!ruleEdit ? (
                <div style={{ color: "#94a3b8", textAlign: "center" as const, padding: "40px 0" }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>📏</div>
                  <div>Links eine Regel auswählen, um sie hier zu bearbeiten.</div>
                </div>
              ) : (
                <div style={{ display: "grid", gap: 16 }}>
                  {/* Row 1: ID + Status */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 16, alignItems: "end" }}>
                    <div>
                      <label style={labelStyle}>Regel-ID</label>
                      <input value={ruleEdit.rule_id ?? ""} disabled style={{ ...inputStyle, background: "#f9fafb", color: "#6b7280" }} />
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0" }}>
                      <label style={{ display: "flex", gap: 8, alignItems: "center", cursor: canWrite ? "pointer" : "default" }}>
                        <input
                          type="checkbox" checked={!!ruleEdit.enabled}
                          onChange={(e) => setRuleEdit({ ...ruleEdit, enabled: e.target.checked })}
                          disabled={!canWrite}
                          style={{ width: 18, height: 18, accentColor: "#16a34a" }}
                        />
                        <span style={{ fontWeight: 700, fontSize: 14, color: ruleEdit.enabled ? "#16a34a" : "#dc2626" }}>
                          {ruleEdit.enabled ? "Aktiv" : "Deaktiviert"}
                        </span>
                      </label>
                    </div>
                  </div>

                  {/* Row 2: Anzeigetext */}
                  <div>
                    <label style={labelStyle}>Anzeigename</label>
                    <input value={ruleEdit.display_name ?? ruleEdit.message ?? ""} onChange={(e) => setRuleEdit({ ...ruleEdit, display_name: e.target.value })} disabled={!canWrite} style={inputStyle} placeholder="Name für die Anzeige" />
                  </div>

                  {/* Row 3: Severity + Category */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                    <div>
                      <label style={labelStyle}>Schweregrad</label>
                      <select value={ruleEdit.severity ?? "WARN"} onChange={(e) => setRuleEdit({ ...ruleEdit, severity: e.target.value as any })} disabled={!canWrite} style={inputStyle}>
                        <option value="CRITICAL">🔴 CRITICAL — Sofortiger Handlungsbedarf</option>
                        <option value="WARN">🟡 WARN — Aufmerksamkeit erforderlich</option>
                        <option value="OK">🟢 OK — Informativ</option>
                      </select>
                    </div>
                    <div>
                      <label style={labelStyle}>Kategorie</label>
                      <select value={ruleEdit.category ?? "medical"} onChange={(e) => setRuleEdit({ ...ruleEdit, category: e.target.value })} disabled={!canWrite} style={inputStyle}>
                        <option value="completeness">📋 Dokumentation</option>
                        <option value="medical">🩺 Klinisch</option>
                      </select>
                    </div>
                  </div>

                  {/* Divider */}
                  <div style={{ borderTop: "1px solid #e5e7eb", margin: "4px 0" }}></div>

                  {/* Row 4: Technical — metric, operator, value */}
                  <div style={{ background: "#f8fafc", padding: 12, borderRadius: 8, border: "1px solid #e2e8f0" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#6b7280", marginBottom: 10 }}>Technische Bedingung</div>
                    <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr", gap: 12 }}>
                      <div>
                        <label style={{ ...labelStyle, fontSize: 11 }}>Metrik (Datenfeld)</label>
                        <input value={ruleEdit.metric ?? ""} onChange={(e) => setRuleEdit({ ...ruleEdit, metric: e.target.value })} disabled={!canWrite} style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12 }} />
                      </div>
                      <div>
                        <label style={{ ...labelStyle, fontSize: 11 }}>Operator</label>
                        <select value={ruleEdit.operator ?? "is_true"} onChange={(e) => setRuleEdit({ ...ruleEdit, operator: e.target.value })} disabled={!canWrite} style={inputStyle}>
                          <option value="is_true">ist wahr</option>
                          <option value="is_false">ist falsch</option>
                          <option value="is_null">fehlt</option>
                          <option value=">">grösser als</option>
                          <option value=">=">grösser/gleich</option>
                        </select>
                      </div>
                      <div>
                        <label style={{ ...labelStyle, fontSize: 11 }}>Wert (JSON)</label>
                        <input value={ruleValueEdit} onChange={(e) => setRuleValueEdit(e.target.value)} disabled={!canWrite} style={{ ...inputStyle, fontFamily: "monospace", fontSize: 12 }} />
                      </div>
                    </div>
                  </div>

                  {/* Row 5: Message + explanation */}
                  <div>
                    <label style={labelStyle}>Meldungstext (kurz)</label>
                    <input value={ruleEdit.message ?? ""} onChange={(e) => setRuleEdit({ ...ruleEdit, message: e.target.value })} disabled={!canWrite} style={inputStyle} />
                  </div>
                  <div>
                    <label style={labelStyle}>Ausführliche Erklärung</label>
                    <textarea value={ruleEdit.explanation ?? ""} onChange={(e) => setRuleEdit({ ...ruleEdit, explanation: e.target.value })} disabled={!canWrite} rows={3} style={{ ...inputStyle, resize: "vertical" as const }} />
                  </div>

                  {/* Save */}
                  <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                    <button onClick={saveRule} disabled={!canWrite} style={{
                      padding: "10px 24px", borderRadius: 8, border: "none",
                      background: canWrite ? "#2563eb" : "#94a3b8", color: "#fff",
                      fontWeight: 700, fontSize: 14, cursor: canWrite ? "pointer" : "not-allowed",
                    }}>
                      💾 Speichern
                    </button>
                    {ruleEdit.updated_at && (
                      <span style={{ fontSize: 11, color: "#94a3b8" }}>
                        Zuletzt geändert: {new Date(ruleEdit.updated_at).toLocaleString("de-CH")}
                        {ruleEdit.updated_by ? ` von ${ruleEdit.updated_by}` : ""}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// Notifications Tab
// ============================================================
function NotificationsTab({ rules, auth, authHeaders, canWrite, onRefresh, onError }: {
  rules: NotificationRuleAdmin[]; auth: AuthState; authHeaders: (a: AuthState) => HeadersInit;
  canWrite: boolean; onRefresh: () => void; onError: (msg: string) => void;
}) {
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newStation, setNewStation] = useState("");
  const [newSeverity, setNewSeverity] = useState("CRITICAL");
  const [newCategory, setNewCategory] = useState("");
  const [newDelay, setNewDelay] = useState(60);
  const [pending, setPending] = useState<any>(null);

  async function addRule() {
    if (!newName.trim() || !newEmail.trim()) return;
    try {
      await apiJson("/api/admin/notifications", {
        method: "POST", headers: authHeaders(auth),
        body: JSON.stringify({
          name: newName.trim(),
          email: newEmail.trim(),
          station_id: newStation.trim() || null,
          min_severity: newSeverity,
          category: newCategory.trim() || null,
          delay_minutes: newDelay,
        }),
      });
      setNewName(""); setNewEmail(""); setNewStation(""); setNewCategory("");
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function toggleActive(id: number, active: boolean) {
    try {
      await apiJson(`/api/admin/notifications/${id}`, {
        method: "PUT", headers: authHeaders(auth),
        body: JSON.stringify({ is_active: !active }),
      });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function deleteRule(id: number) {
    if (!window.confirm("Benachrichtigungsregel löschen?")) return;
    try {
      await apiJson(`/api/admin/notifications/${id}`, { method: "DELETE", headers: authHeaders(auth) });
      onRefresh();
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  async function loadPending() {
    try {
      const data = await apiJson<any>("/api/admin/notifications/pending", { method: "GET", headers: authHeaders(auth) });
      setPending(data);
    } catch (e: any) { onError(e?.message ?? String(e)); }
  }

  return (
    <SectionCard title="E-Mail-Benachrichtigungen">
      <div style={{ fontSize: 13, color: "#64748b", marginBottom: 12 }}>
        Konfigurieren Sie, wer bei welchen Alerts per E-Mail benachrichtigt wird.
        <br />
        <strong style={{ color: "#b45309" }}>Hinweis:</strong> SMTP-Server noch nicht konfiguriert — Regeln werden gespeichert, aber aktuell noch kein Versand.
      </div>

      {/* Existing rules */}
      {rules.length > 0 && (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, marginBottom: 16 }}>
          <thead>
            <tr>
              {["Name", "E-Mail", "Station", "Min. Severity", "Kategorie", "Verzögerung", "Aktiv", "Aktionen"].map(h => (
                <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0", padding: "8px 6px", color: "#64748b" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rules.map((r) => (
              <tr key={r.id}>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2", fontWeight: 600 }}>{r.name}</td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{r.email}</td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{r.station_id ?? "Alle"}</td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                  <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 999, background: r.min_severity === "CRITICAL" ? "#fee2e2" : "#fef3c7", color: r.min_severity === "CRITICAL" ? "#b91c1c" : "#92400e" }}>
                    {r.min_severity}
                  </span>
                </td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2", color: "#64748b" }}>{r.category ?? "Alle"}</td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>{r.delay_minutes} min</td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                  <button onClick={() => toggleActive(r.id, r.is_active)} disabled={!canWrite} style={{ background: "none", border: "none", cursor: canWrite ? "pointer" : "default", fontSize: 14 }}>
                    {r.is_active ? "✅" : "❌"}
                  </button>
                </td>
                <td style={{ padding: "8px 6px", borderBottom: "1px solid #f2f2f2" }}>
                  <button onClick={() => deleteRule(r.id)} disabled={!canWrite} style={{ padding: "4px 8px", borderRadius: 6, border: "1px solid #fecaca", background: "#fff1f2", color: "#b42318", fontSize: 11, cursor: canWrite ? "pointer" : "not-allowed" }}>Löschen</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {rules.length === 0 && (
        <div style={{ padding: 16, background: "#f8fafc", borderRadius: 8, marginBottom: 16, color: "#64748b", textAlign: "center" }}>
          Noch keine Benachrichtigungsregeln konfiguriert.
        </div>
      )}

      {/* Add new rule */}
      {canWrite && (
        <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 14, marginBottom: 16 }}>
          <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 10 }}>Neue Regel hinzufügen</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 10 }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Name / Empfänger</label>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="z.B. Stationsleitung A1" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: "100%", boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>E-Mail-Adresse</label>
              <input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="name@spital.ch" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: "100%", boxSizing: "border-box" }} />
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Station (leer = alle)</label>
              <input value={newStation} onChange={(e) => setNewStation(e.target.value)} placeholder="z.B. A1" style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: "100%", boxSizing: "border-box" }} />
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Min. Severity</label>
              <select value={newSeverity} onChange={(e) => setNewSeverity(e.target.value)} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6 }}>
                <option value="CRITICAL">Nur CRITICAL</option>
                <option value="WARN">WARN + CRITICAL</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Kategorie (leer = alle)</label>
              <select value={newCategory} onChange={(e) => setNewCategory(e.target.value)} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6 }}>
                <option value="">Alle</option>
                <option value="completeness">Vollständigkeit</option>
                <option value="medical">Medizinisch</option>
              </select>
            </div>
            <div>
              <label style={{ fontSize: 11, fontWeight: 700, display: "block" }}>Verzögerung (Min.)</label>
              <input type="number" min={0} value={newDelay} onChange={(e) => setNewDelay(Number(e.target.value))} style={{ padding: 6, border: "1px solid #ccc", borderRadius: 6, width: 80 }} />
            </div>
            <button onClick={addRule} style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid #3b82f6", background: "#3b82f6", color: "#fff", fontWeight: 700, cursor: "pointer" }}>+ Hinzufügen</button>
          </div>
        </div>
      )}

      {/* Pending preview */}
      <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 14 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
          <button onClick={loadPending} style={{ padding: "6px 12px", borderRadius: 6, border: "1px solid #ccc", background: "#f8fafc", cursor: "pointer", fontSize: 12 }}>
            Fällige Benachrichtigungen anzeigen (Vorschau)
          </button>
          {pending && <span style={{ fontSize: 12, color: "#64748b" }}>{pending.count} fällig · {pending.note}</span>}
        </div>
        {pending?.pending?.length > 0 && (
          <div style={{ maxHeight: 250, overflow: "auto", fontSize: 12 }}>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Regel", "E-Mail", "Station", "Fall", "Alert", "Severity"].map(h => (
                    <th key={h} style={{ textAlign: "left", borderBottom: "2px solid #e2e8f0", padding: "6px 4px", color: "#64748b" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pending.pending.map((p: any, i: number) => (
                  <tr key={i}>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{p.rule_name}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{p.email}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{p.station_id}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2", fontWeight: 600 }}>{p.case_id}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{p.message}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                      <span style={{ fontSize: 11, padding: "2px 6px", borderRadius: 999, background: p.severity === "CRITICAL" ? "#fee2e2" : "#fef3c7", color: p.severity === "CRITICAL" ? "#b91c1c" : "#92400e" }}>{p.severity}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </SectionCard>
  );
}
