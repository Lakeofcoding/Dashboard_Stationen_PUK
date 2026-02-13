import { useEffect, useMemo, useState } from "react";

type AuthState = { stationId: string; userId: string };
type MetaMe = { user_id: string; station_id: string; roles: string[]; permissions: string[]; break_glass: boolean };

type Props = {
  auth: AuthState;
  authHeaders: (auth: AuthState) => HeadersInit;
  me: MetaMe | null;
};

type AdminUser = {
  user_id: string;
  display_name: string | null;
  is_active: boolean;
  created_at: string;
  roles: { role_id: string; station_id: string }[];
};

type AdminRole = {
  role_id: string;
  description: string | null;
  permissions: string[];
  is_system: boolean;
};

type AdminPermission = {
  perm_id: string;
  description: string | null;
  is_system: boolean;
};

type RuleDef = {
  rule_id: string;
  display_name: string | null;
  message: string;
  explanation: string;
  category: string;
  severity: "OK" | "WARN" | "CRITICAL";
  metric: string;
  operator: string;
  value_json: string;
  enabled: boolean;
  is_system: boolean;
  updated_at: string | null;
  updated_by: string | null;
};

type AuditEvent = {
  event_id: string;
  ts: string;
  actor_user_id: string | null;
  actor_station_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  success: boolean;
  message: string | null;
  details: string | null;
};

async function apiJson<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

function FieldLabel({ label, hint }: { label: string; hint?: string }) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#334155" }}>{label}</div>
      {hint ? <div style={{ fontSize: 11, color: "#64748b" }}>{hint}</div> : null}
    </div>
  );
}

export function AdminPanel({ auth, authHeaders, me }: Props) {
  const canRead = useMemo(() => new Set(me?.permissions ?? []).has("admin:read"), [me]);
  const canWrite = useMemo(() => new Set(me?.permissions ?? []).has("admin:write"), [me]);

  const [tab, setTab] = useState<"users" | "roles" | "rules" | "audit">("users");
  const [error, setError] = useState<string | null>(null);

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [permissions, setPermissions] = useState<AdminPermission[]>([]);
  const [rules, setRules] = useState<RuleDef[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);

  // -------------------------
  // Loading
  // -------------------------

  async function refreshAll() {
    setError(null);
    if (!canRead) return;
    try {
      const u = await apiJson<{ users: AdminUser[] }>("/api/admin/users", { method: "GET", headers: authHeaders(auth) });
      setUsers(u.users);
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
    try {
      const r = await apiJson<{ roles: AdminRole[] }>("/api/admin/roles", { method: "GET", headers: authHeaders(auth) });
      setRoles(r.roles);
    } catch {
      // ignore
    }
    try {
      const p = await apiJson<{ permissions: AdminPermission[] }>("/api/admin/permissions", { method: "GET", headers: authHeaders(auth) });
      setPermissions(p.permissions);
    } catch {
      // ignore
    }
    try {
      const rr = await apiJson<{ rules: RuleDef[] }>("/api/admin/rules", { method: "GET", headers: authHeaders(auth) });
      setRules(rr.rules);
    } catch {
      // ignore
    }
    try {
      const a = await apiJson<{ events: AuditEvent[] }>("/api/admin/audit?limit=200", { method: "GET", headers: authHeaders(auth) });
      setAudit(a.events);
    } catch {
      // audit might be forbidden
    }
  }

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.stationId, auth.userId]);

  // -------------------------
  // Users
  // -------------------------

  const [createUserId, setCreateUserId] = useState("");
  const [createDisplayName, setCreateDisplayName] = useState("");
  const [createInitialRole, setCreateInitialRole] = useState("viewer");
  const [createInitialStation, setCreateInitialStation] = useState("*");

  async function createUser() {
    setError(null);
    try {
      await apiJson("/api/admin/users", {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({
          user_id: createUserId.trim(),
          display_name: createDisplayName.trim() || null,
          is_active: true,
          roles: [{ role_id: createInitialRole, station_id: createInitialStation || "*" }],
        }),
      });
      setCreateUserId("");
      setCreateDisplayName("");
      setCreateInitialRole("viewer");
      setCreateInitialStation("*");
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  const [assignUserId, setAssignUserId] = useState("");
  const [assignRoleId, setAssignRoleId] = useState("viewer");
  const [assignStationId, setAssignStationId] = useState("*");

  async function assignRole() {
    setError(null);
    try {
      await apiJson(`/api/admin/users/${encodeURIComponent(assignUserId)}/roles`, {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({ role_id: assignRoleId, station_id: assignStationId || "*" }),
      });
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function removeRole(userId: string, roleId: string, stationId: string) {
    if (!window.confirm(`Rolle entfernen?\n\nUser: ${userId}\nRolle: ${roleId}\nStation: ${stationId}`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/users/${encodeURIComponent(userId)}/roles/${encodeURIComponent(roleId)}/${encodeURIComponent(stationId)}`, {
        method: "DELETE",
        headers: authHeaders(auth),
      });
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function deleteUser(userId: string) {
    if (!window.confirm(`User löschen?\n\n${userId}\n\nHinweis: Rollen-Zuweisungen werden mit gelöscht.`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/users/${encodeURIComponent(userId)}`, { method: "DELETE", headers: authHeaders(auth) });
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  // -------------------------
  // Roles & Permissions
  // -------------------------

  const [createRoleId, setCreateRoleId] = useState("");
  const [createRoleDesc, setCreateRoleDesc] = useState("");
  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const selectedRole = useMemo(() => roles.find((r) => r.role_id === selectedRoleId) ?? null, [roles, selectedRoleId]);
  const [roleDescEdit, setRoleDescEdit] = useState("");
  const [rolePermsEdit, setRolePermsEdit] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!selectedRole) return;
    setRoleDescEdit(selectedRole.description ?? "");
    setRolePermsEdit(new Set(selectedRole.permissions ?? []));
  }, [selectedRole]);

  async function createRole() {
    setError(null);
    try {
      const rid = createRoleId.trim();
      if (!rid) return;
      await apiJson(`/api/admin/roles`, {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({ role_id: rid, description: createRoleDesc.trim() || null }),
      });
      setCreateRoleId("");
      setCreateRoleDesc("");
      await refreshAll();
      setSelectedRoleId(rid);
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function saveRole() {
    if (!selectedRole) return;
    if (selectedRole.is_system) {
      setError("System-Rollen können nicht geändert werden.");
      return;
    }
    setError(null);
    try {
      await apiJson(`/api/admin/roles/${encodeURIComponent(selectedRole.role_id)}`, {
        method: "PUT",
        headers: authHeaders(auth),
        body: JSON.stringify({ description: roleDescEdit }),
      });
      await apiJson(`/api/admin/roles/${encodeURIComponent(selectedRole.role_id)}/permissions`, {
        method: "PUT",
        headers: authHeaders(auth),
        body: JSON.stringify({ permissions: Array.from(rolePermsEdit.values()).sort() }),
      });
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function deleteRole(roleId: string) {
    if (!window.confirm(`Rolle löschen?\n\n${roleId}\n\nHinweis: Zuweisungen und Role->Permission mappings werden gelöscht.`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/roles/${encodeURIComponent(roleId)}`, { method: "DELETE", headers: authHeaders(auth) });
      setSelectedRoleId(null);
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  const [createPermId, setCreatePermId] = useState("");
  const [createPermDesc, setCreatePermDesc] = useState("");
  async function createPermission() {
    setError(null);
    try {
      const pid = createPermId.trim();
      if (!pid) return;
      await apiJson(`/api/admin/permissions`, {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({ perm_id: pid, description: createPermDesc.trim() || null }),
      });
      setCreatePermId("");
      setCreatePermDesc("");
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function deletePermission(permId: string) {
    if (!window.confirm(`Permission löschen?\n\n${permId}\n\nHinweis: wird aus allen Rollen entfernt.`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/permissions/${encodeURIComponent(permId)}`, { method: "DELETE", headers: authHeaders(auth) });
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  // -------------------------
  // Rules
  // -------------------------

  const [ruleQuery, setRuleQuery] = useState("");
  const filteredRules = useMemo(() => {
    const q = ruleQuery.trim().toLowerCase();
    if (!q) return rules;
    return rules.filter((r) => (r.rule_id + " " + (r.display_name ?? "") + " " + (r.message ?? "")).toLowerCase().includes(q));
  }, [rules, ruleQuery]);

  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const selectedRule = useMemo(() => rules.find((r) => r.rule_id === selectedRuleId) ?? null, [rules, selectedRuleId]);

  const [ruleEdit, setRuleEdit] = useState<RuleDef | null>(null);
  const [ruleValueEdit, setRuleValueEdit] = useState<string>("");
  useEffect(() => {
    if (!selectedRule) {
      setRuleEdit(null);
      setRuleValueEdit("");
      return;
    }
    setRuleEdit({ ...selectedRule });
    setRuleValueEdit(selectedRule.value_json ?? "null");
  }, [selectedRule]);

  function newRuleDraft() {
    const draft: RuleDef = {
      rule_id: "NEW_RULE_ID",
      display_name: null,
      message: "",
      explanation: "",
      category: "medical",
      severity: "WARN",
      metric: "",
      operator: "is_true",
      value_json: "true",
      enabled: true,
      is_system: false,
      updated_at: null,
      updated_by: null,
    };
    setSelectedRuleId(null);
    setRuleEdit(draft);
    setRuleValueEdit(draft.value_json);
  }

  async function saveRule() {
    if (!ruleEdit) return;
    if (!canWrite) return;
    setError(null);

    let parsed: any = null;
    try {
      parsed = JSON.parse(ruleValueEdit.trim() || "null");
    } catch (e: any) {
      setError(`Value ist kein gültiges JSON: ${String(e?.message ?? e)}`);
      return;
    }

    try {
      const rid = ruleEdit.rule_id.trim();
      if (!rid) {
        setError("rule_id fehlt");
        return;
      }
      await apiJson(`/api/admin/rules/${encodeURIComponent(rid)}`, {
        method: "PUT",
        headers: authHeaders(auth),
        body: JSON.stringify({
          rule_id: rid,
          display_name: ruleEdit.display_name?.trim() || null,
          message: ruleEdit.message,
          explanation: ruleEdit.explanation,
          category: ruleEdit.category,
          severity: ruleEdit.severity,
          metric: ruleEdit.metric,
          operator: ruleEdit.operator,
          value: parsed,
          enabled: !!ruleEdit.enabled,
        }),
      });
      await refreshAll();
      setSelectedRuleId(rid);
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function deleteRule(ruleId: string, isSystem: boolean) {
    if (isSystem) {
      setError("System-Regeln können nicht gelöscht werden (nur deaktivieren oder editieren).");
      return;
    }
    if (!window.confirm(`Regel löschen?\n\n${ruleId}`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/rules/${encodeURIComponent(ruleId)}`, { method: "DELETE", headers: authHeaders(auth) });
      setSelectedRuleId(null);
      setRuleEdit(null);
      await refreshAll();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  // -------------------------
  // Render
  // -------------------------

  if (!canRead) {
    return (
      <div style={{ padding: 12 }}>
        <h2 style={{ marginTop: 0 }}>Admin</h2>
        <p style={{ color: "#b91c1c" }}>Keine Berechtigung: <code>admin:read</code> fehlt.</p>
      </div>
    );
  }

  return (
    <div style={{ padding: 12 }}>
      <h2 style={{ marginTop: 0 }}>Admin</h2>
      <div style={{ fontSize: 13, opacity: 0.8 }}>
        Eingeloggt als <code>{me?.user_id ?? auth.userId}</code> (Station <code>{me?.station_id ?? auth.stationId}</code>)
      </div>

      {error ? <p style={{ color: "#b91c1c" }}>Fehler: {error}</p> : null}

      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
        {(
          [
            { id: "users", label: "Users" },
            { id: "roles", label: "Rollen & Permissions" },
            { id: "rules", label: "Rules" },
            { id: "audit", label: "Audit" },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              padding: "6px 10px",
              borderRadius: 10,
              border: "1px solid #cbd5e1",
              background: tab === t.id ? "#eef6ff" : "#fff",
              cursor: "pointer",
              fontWeight: tab === t.id ? 700 : 600,
            }}
          >
            {t.label}
          </button>
        ))}
        <button
          onClick={refreshAll}
          style={{
            marginLeft: "auto",
            padding: "6px 10px",
            borderRadius: 10,
            border: "1px solid #cbd5e1",
            background: "#fff",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Refresh
        </button>
      </div>

      {/* USERS */}
      {tab === "users" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12, marginTop: 12 }}>
          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>User anlegen</h3>
            {!canWrite ? <div style={{ color: "#64748b", fontSize: 12 }}>Nur Read: <code>admin:write</code> fehlt.</div> : null}

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr auto", gap: 10, alignItems: "end" }}>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="User-ID" hint="stabiler Identifier (z.B. AD-Login)" />
                <input value={createUserId} onChange={(e) => setCreateUserId(e.target.value)} placeholder="demo2" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="Display Name" hint="optional" />
                <input value={createDisplayName} onChange={(e) => setCreateDisplayName(e.target.value)} placeholder="Max Muster" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="Initiale Rolle" hint="wird direkt zugewiesen" />
                <select value={createInitialRole} onChange={(e) => setCreateInitialRole(e.target.value)} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
                  {roles.map((r) => (
                    <option key={r.role_id} value={r.role_id}>
                      {r.role_id}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="Station" hint="* = alle Stationen" />
                <input value={createInitialStation} onChange={(e) => setCreateInitialStation(e.target.value)} placeholder="*" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              </div>
              <button onClick={createUser} disabled={!canWrite || !createUserId.trim()} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 700 }}>
                Create
              </button>
            </div>
          </section>

          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Rolle zuweisen</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 10, alignItems: "end" }}>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="User" hint="bestehender User" />
                <select value={assignUserId} onChange={(e) => setAssignUserId(e.target.value)} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
                  <option value="">— wählen —</option>
                  {users.map((u) => (
                    <option key={u.user_id} value={u.user_id}>
                      {u.user_id}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="Rolle" hint="role_id" />
                <select value={assignRoleId} onChange={(e) => setAssignRoleId(e.target.value)} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
                  {roles.map((r) => (
                    <option key={r.role_id} value={r.role_id}>
                      {r.role_id}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ display: "grid", gap: 6 }}>
                <FieldLabel label="Station" hint="* oder konkreter Code" />
                <input value={assignStationId} onChange={(e) => setAssignStationId(e.target.value)} placeholder="*" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              </div>
              <button onClick={assignRole} disabled={!canWrite || !assignUserId.trim() || !assignRoleId.trim()} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 700 }}>
                Assign
              </button>
            </div>
          </section>

          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Users</h3>
            <div style={{ maxHeight: 460, overflow: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>User</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>Rollen</th>
                    <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id}>
                      <td style={{ verticalAlign: "top", padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                        <div>
                          <code>{u.user_id}</code> {u.display_name ? `· ${u.display_name}` : ""}
                        </div>
                        <div style={{ opacity: 0.7 }}>{u.is_active ? "active" : "disabled"}</div>
                      </td>
                      <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                          {u.roles.map((r) => (
                            <span key={`${r.role_id}:${r.station_id}`} style={{ border: "1px solid #ddd", borderRadius: 999, padding: "2px 8px" }}>
                              <code>{r.role_id}</code> <span style={{ opacity: 0.7 }}>({r.station_id})</span>
                              {canWrite ? (
                                <button style={{ marginLeft: 6 }} onClick={() => removeRole(u.user_id, r.role_id, r.station_id)}>
                                  ×
                                </button>
                              ) : null}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                        {canWrite ? (
                          <button onClick={() => deleteUser(u.user_id)} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff1f2", cursor: "pointer", fontWeight: 700 }}>
                            Delete
                          </button>
                        ) : (
                          <span style={{ color: "#64748b" }}>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}

      {/* ROLES */}
      {tab === "roles" && (
        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 12, marginTop: 12 }}>
          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Rollen</h3>
            <div style={{ display: "grid", gap: 10 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 8, alignItems: "end" }}>
                <div style={{ display: "grid", gap: 6 }}>
                  <FieldLabel label="Neue Rolle" hint="role_id (z.B. reporting_viewer)" />
                  <input value={createRoleId} onChange={(e) => setCreateRoleId(e.target.value)} placeholder="custom_role" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                </div>
                <div style={{ display: "grid", gap: 6 }}>
                  <FieldLabel label="Beschreibung" hint="optional" />
                  <input value={createRoleDesc} onChange={(e) => setCreateRoleDesc(e.target.value)} placeholder="..." style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                </div>
                <button onClick={createRole} disabled={!canWrite || !createRoleId.trim()} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 700 }}>
                  Create
                </button>
              </div>

              <div style={{ maxHeight: 480, overflow: "auto", borderTop: "1px solid #f1f5f9", paddingTop: 10 }}>
                {roles.map((r) => (
                  <div
                    key={r.role_id}
                    onClick={() => setSelectedRoleId(r.role_id)}
                    style={{
                      padding: "8px 10px",
                      borderRadius: 10,
                      border: "1px solid #e2e8f0",
                      cursor: "pointer",
                      background: selectedRoleId === r.role_id ? "#eef6ff" : "#fff",
                      marginBottom: 8,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                      <code>{r.role_id}</code>
                      {r.is_system ? <span style={{ fontSize: 11, color: "#64748b" }}>system</span> : <span style={{ fontSize: 11, color: "#64748b" }}>custom</span>}
                    </div>
                    {r.description ? <div style={{ fontSize: 12, color: "#475569" }}>{r.description}</div> : null}
                    <div style={{ fontSize: 11, color: "#64748b" }}>{(r.permissions ?? []).length} permissions</div>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Role Editor</h3>
            {!selectedRole ? (
              <div style={{ color: "#64748b" }}>Wähle links eine Rolle aus.</div>
            ) : (
              <div style={{ display: "grid", gap: 12 }}>
                {selectedRole.is_system ? (
                  <div style={{ padding: 10, borderRadius: 10, border: "1px solid #e2e8f0", background: "#f8fafc", color: "#64748b", fontSize: 12 }}>
                    System-Rolle: Permissions können hier nicht geändert werden (Schutz vor Startup-Seed-Überschreibung).
                  </div>
                ) : null}

                <div style={{ display: "grid", gap: 6, maxWidth: 700 }}>
                  <FieldLabel label="Beschreibung" />
                  <input value={roleDescEdit} onChange={(e) => setRoleDescEdit(e.target.value)} disabled={!canWrite || selectedRole.is_system} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                </div>

                <div style={{ display: "grid", gap: 8 }}>
                  <FieldLabel label="Permissions" hint="Nur für custom Rollen editierbar" />
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(260px, 1fr))", gap: 8 }}>
                    {permissions.map((p) => {
                      const checked = rolePermsEdit.has(p.perm_id);
                      const disabled = !canWrite || selectedRole.is_system;
                      return (
                        <label key={p.perm_id} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: 8, border: "1px solid #e2e8f0", borderRadius: 10 }}>
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={disabled}
                            onChange={(e) => {
                              const next = new Set(rolePermsEdit);
                              if (e.target.checked) next.add(p.perm_id);
                              else next.delete(p.perm_id);
                              setRolePermsEdit(next);
                            }}
                            style={{ marginTop: 3 }}
                          />
                          <div style={{ display: "grid", gap: 2 }}>
                            <code>{p.perm_id}</code>
                            <div style={{ fontSize: 11, color: "#64748b" }}>{p.description ?? "—"}</div>
                            {p.is_system ? <div style={{ fontSize: 11, color: "#94a3b8" }}>system permission</div> : null}
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>

                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <button onClick={saveRole} disabled={!canWrite || selectedRole.is_system} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 800 }}>
                    Save
                  </button>
                  {!selectedRole.is_system ? (
                    <button onClick={() => deleteRole(selectedRole.role_id)} disabled={!canWrite} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff1f2", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 800 }}>
                      Delete Role
                    </button>
                  ) : null}
                </div>

                <hr style={{ border: "none", borderTop: "1px solid #e2e8f0" }} />

                <h4 style={{ margin: 0 }}>Permissions anlegen</h4>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr auto", gap: 8, alignItems: "end", maxWidth: 820 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="Permission ID" hint="z.B. reports:view" />
                    <input value={createPermId} onChange={(e) => setCreatePermId(e.target.value)} placeholder="feature_x:use" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="Beschreibung" hint="optional" />
                    <input value={createPermDesc} onChange={(e) => setCreatePermDesc(e.target.value)} placeholder="..." style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                  </div>
                  <button onClick={createPermission} disabled={!canWrite || !createPermId.trim()} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 800 }}>
                    Create
                  </button>
                </div>

                <div style={{ marginTop: 10, maxHeight: 280, overflow: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                    <thead>
                      <tr>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>perm_id</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>description</th>
                        <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {permissions.map((p) => (
                        <tr key={p.perm_id}>
                          <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                            <code>{p.perm_id}</code>
                            {p.is_system ? <span style={{ marginLeft: 8, fontSize: 11, color: "#94a3b8" }}>system</span> : null}
                          </td>
                          <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{p.description ?? "—"}</td>
                          <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                            {!p.is_system && canWrite ? (
                              <button onClick={() => deletePermission(p.perm_id)} style={{ padding: "6px 10px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff1f2", cursor: "pointer", fontWeight: 700 }}>
                                Delete
                              </button>
                            ) : (
                              <span style={{ color: "#64748b" }}>—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {/* RULES */}
      {tab === "rules" && (
        <div style={{ display: "grid", gridTemplateColumns: "420px 1fr", gap: 12, marginTop: 12 }}>
          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Rules</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input value={ruleQuery} onChange={(e) => setRuleQuery(e.target.value)} placeholder="Suche rule_id / Titel ..." style={{ flex: 1, padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              {canWrite ? (
                <button onClick={newRuleDraft} style={{ padding: "8px 10px", borderRadius: 10, border: "1px solid #cbd5e1", background: "#eef6ff", cursor: "pointer", fontWeight: 800 }}>
                  New
                </button>
              ) : null}
            </div>

            <div style={{ marginTop: 10, maxHeight: 520, overflow: "auto" }}>
              {filteredRules.map((r) => (
                <div
                  key={r.rule_id}
                  onClick={() => setSelectedRuleId(r.rule_id)}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 10,
                    border: "1px solid #e2e8f0",
                    cursor: "pointer",
                    background: selectedRuleId === r.rule_id ? "#eef6ff" : "#fff",
                    marginBottom: 8,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                    <code>{r.rule_id}</code>
                    <span style={{ fontSize: 11, color: r.enabled ? "#15803d" : "#b91c1c" }}>{r.enabled ? "enabled" : "disabled"}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#475569" }}>{r.display_name ?? r.message}</div>
                  <div style={{ fontSize: 11, color: "#64748b" }}>{r.category} · {r.severity}</div>
                </div>
              ))}
            </div>
          </section>

          <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
            <h3 style={{ marginTop: 0 }}>Rule Editor</h3>
            {!ruleEdit ? (
              <div style={{ color: "#64748b" }}>Wähle links eine Regel aus oder klicke „New“.</div>
            ) : (
              <div style={{ display: "grid", gap: 12, maxWidth: 900 }}>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="rule_id" hint="stabiler Schlüssel (UI+Engine)" />
                    <input value={ruleEdit.rule_id} onChange={(e) => setRuleEdit({ ...ruleEdit, rule_id: e.target.value })} disabled={!canWrite || (selectedRule?.is_system ?? false)} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                    {(selectedRule?.is_system ?? false) ? <div style={{ fontSize: 11, color: "#94a3b8" }}>System-Regel: rule_id nicht änderbar</div> : null}
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="enabled" hint="deaktiviert unterdrückt die Regel" />
                    <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <input type="checkbox" checked={!!ruleEdit.enabled} onChange={(e) => setRuleEdit({ ...ruleEdit, enabled: e.target.checked })} disabled={!canWrite} />
                      <span style={{ color: ruleEdit.enabled ? "#15803d" : "#b91c1c", fontWeight: 700 }}>{ruleEdit.enabled ? "enabled" : "disabled"}</span>
                    </label>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="display_name" hint="Titel im UI (Fallback: message)" />
                    <input value={ruleEdit.display_name ?? ""} onChange={(e) => setRuleEdit({ ...ruleEdit, display_name: e.target.value || null })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="category" hint="completeness / medical (frei)" />
                    <input value={ruleEdit.category} onChange={(e) => setRuleEdit({ ...ruleEdit, category: e.target.value })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="severity" hint="WARN / CRITICAL" />
                    <select value={ruleEdit.severity} onChange={(e) => setRuleEdit({ ...ruleEdit, severity: e.target.value as RuleDef["severity"] })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
                      <option value="WARN">WARN</option>
                      <option value="CRITICAL">CRITICAL</option>
                      <option value="OK">OK</option>
                    </select>
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="operator" hint="is_true / is_null / > / >= ..." />
                    <select value={ruleEdit.operator} onChange={(e) => setRuleEdit({ ...ruleEdit, operator: e.target.value })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
                      <option value="is_true">is_true</option>
                      <option value="is_false">is_false</option>
                      <option value="is_null">is_null</option>
                      <option value=">">&gt;</option>
                      <option value=">=">&gt;=</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="metric" hint="derived metric key (Backend)" />
                    <input value={ruleEdit.metric} onChange={(e) => setRuleEdit({ ...ruleEdit, metric: e.target.value })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                  </div>
                  <div style={{ display: "grid", gap: 6 }}>
                    <FieldLabel label="value (JSON)" hint={'Beispiele: true, 5, "abc", null'} />
                    <input value={ruleValueEdit} onChange={(e) => setRuleValueEdit(e.target.value)} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc", fontFamily: "monospace" }} />
                  </div>
                </div>

                <div style={{ display: "grid", gap: 6 }}>
                  <FieldLabel label="message" hint="Kurztext (Fallback wenn display_name leer)" />
                  <input value={ruleEdit.message} onChange={(e) => setRuleEdit({ ...ruleEdit, message: e.target.value })} disabled={!canWrite} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                </div>

                <div style={{ display: "grid", gap: 6 }}>
                  <FieldLabel label="explanation" hint="Langtext" />
                  <textarea value={ruleEdit.explanation} onChange={(e) => setRuleEdit({ ...ruleEdit, explanation: e.target.value })} disabled={!canWrite} rows={4} style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                </div>

                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <button onClick={saveRule} disabled={!canWrite} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #cbd5e1", background: canWrite ? "#eef6ff" : "#f1f5f9", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 800 }}>
                    Save
                  </button>
                  {selectedRule ? (
                    <button onClick={() => deleteRule(selectedRule.rule_id, selectedRule.is_system)} disabled={!canWrite} style={{ padding: "8px 12px", borderRadius: 10, border: "1px solid #fecaca", background: "#fff1f2", cursor: canWrite ? "pointer" : "not-allowed", fontWeight: 800 }}>
                      Delete
                    </button>
                  ) : null}
                  {ruleEdit.updated_at ? (
                    <div style={{ marginLeft: "auto", fontSize: 12, color: "#64748b" }}>
                      last update: {ruleEdit.updated_at} by <code>{ruleEdit.updated_by ?? "—"}</code>
                    </div>
                  ) : null}
                </div>
              </div>
            )}
          </section>
        </div>
      )}

      {/* AUDIT */}
      {tab === "audit" && (
        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff", marginTop: 12 }}>
          <h3 style={{ marginTop: 0 }}>Audit</h3>
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
            Zeigt die letzten Events. Falls hier nichts angezeigt wird, fehlt wahrscheinlich <code>audit:read</code>.
          </div>

          <div style={{ maxHeight: 520, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>ts</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>action</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>actor</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>target</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>ok</th>
                </tr>
              </thead>
              <tbody>
                {audit.map((e) => (
                  <tr key={e.event_id}>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2", whiteSpace: "nowrap" }}>{e.ts}</td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                      <code>{e.action}</code>
                      {e.message ? <div style={{ opacity: 0.7 }}>{e.message}</div> : null}
                      {e.details ? <div style={{ opacity: 0.7, fontFamily: "monospace" }}>{e.details}</div> : null}
                    </td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                      <code>{e.actor_user_id ?? "—"}</code>
                      <div style={{ opacity: 0.7 }}>{e.actor_station_id ?? "—"}</div>
                    </td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>
                      <div style={{ opacity: 0.8 }}>{e.target_type ?? "—"}</div>
                      <div style={{ opacity: 0.8 }}>{e.target_id ?? "—"}</div>
                    </td>
                    <td style={{ padding: "6px 4px", borderBottom: "1px solid #f2f2f2" }}>{e.success ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
