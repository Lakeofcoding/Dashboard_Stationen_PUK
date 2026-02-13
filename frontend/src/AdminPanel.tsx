
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

export function AdminPanel({ auth, authHeaders, me }: Props) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const canWrite = useMemo(() => new Set(me?.permissions ?? []).has("admin:write"), [me]);

  const [newUserId, setNewUserId] = useState("");
  const [newUserName, setNewUserName] = useState("");
  const [assignUserId, setAssignUserId] = useState("");
  const [assignRoleId, setAssignRoleId] = useState("viewer");
  const [assignStationId, setAssignStationId] = useState("*");

  async function refresh() {
    setError(null);
    try {
      const u = await apiJson<{ users: AdminUser[] }>("/api/admin/users", { method: "GET", headers: authHeaders(auth) });
      setUsers(u.users);
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
    try {
      const a = await apiJson<{ events: AuditEvent[] }>("/api/admin/audit?limit=200", { method: "GET", headers: authHeaders(auth) });
      setAudit(a.events);
    } catch (e: any) {
      // audit might be forbidden
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.stationId, auth.userId]);

  async function createUser() {
    setError(null);
    try {
      await apiJson("/api/admin/users", {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({ user_id: newUserId, display_name: newUserName || null, is_active: true }),
      });
      setNewUserId("");
      setNewUserName("");
      await refresh();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function assignRole() {
    setError(null);
    try {
      await apiJson(`/api/admin/users/${encodeURIComponent(assignUserId)}/roles`, {
        method: "POST",
        headers: authHeaders(auth),
        body: JSON.stringify({ role_id: assignRoleId, station_id: assignStationId }),
      });
      await refresh();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  async function removeRole(userId: string, roleId: string, stationId: string) {
    if (!window.confirm(`Remove role ${roleId} (${stationId}) from ${userId}?`)) return;
    setError(null);
    try {
      await apiJson(`/api/admin/users/${encodeURIComponent(userId)}/roles/${encodeURIComponent(roleId)}/${encodeURIComponent(stationId)}`, {
        method: "DELETE",
        headers: authHeaders(auth),
      });
      await refresh();
    } catch (e: any) {
      setError(String(e?.message ?? e));
    }
  }

  return (
    <div style={{ padding: 12 }}>
      <h2 style={{ marginTop: 0 }}>Admin</h2>
      <div style={{ fontSize: 13, opacity: 0.8 }}>
        Eingeloggt als <code>{me?.user_id ?? auth.userId}</code> (Station <code>{me?.station_id ?? auth.stationId}</code>)
      </div>

      {error && <p style={{ color: "red" }}>Fehler: {error}</p>}

      <div style={{ display: "grid", gap: 12, gridTemplateColumns: "1fr 1fr" }}>
        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>Users</h3>

          {canWrite && (
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr auto", alignItems: "center" }}>
              <input value={newUserId} onChange={(e) => setNewUserId(e.target.value)} placeholder="user_id" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              <input value={newUserName} onChange={(e) => setNewUserName(e.target.value)} placeholder="display_name" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
              <button className="btn" onClick={createUser} disabled={!newUserId.trim()}>
                Create
              </button>
            </div>
          )}

          <div style={{ marginTop: 10, maxHeight: 420, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>User</th>
                  <th style={{ textAlign: "left", borderBottom: "1px solid #eee", padding: "6px 4px" }}>Roles</th>
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
                            {canWrite && (
                              <button style={{ marginLeft: 6 }} onClick={() => removeRole(u.user_id, r.role_id, r.station_id)}>
                                ×
                              </button>
                            )}
                          </span>
                        ))}
                      </div>
                      {canWrite && (
                        <div style={{ marginTop: 8, display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 8 }}>
                          <input value={assignUserId} onChange={(e) => setAssignUserId(e.target.value)} placeholder="user_id" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                          <input value={assignRoleId} onChange={(e) => setAssignRoleId(e.target.value)} placeholder="role_id" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                          <input value={assignStationId} onChange={(e) => setAssignStationId(e.target.value)} placeholder="station_id or *" style={{ padding: 8, borderRadius: 10, border: "1px solid #ccc" }} />
                          <button className="btn" onClick={assignRole} disabled={!assignUserId.trim() || !assignRoleId.trim()}>
                            Assign
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button className="btn" style={{ marginTop: 10 }} onClick={refresh}>
            Refresh
          </button>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12, background: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>Audit</h3>
          <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 8 }}>
            Zeigt die letzten Events (RBAC Deny, Admin Actions, Break-glass). Falls dir hier nichts angezeigt wird, fehlt wahrscheinlich <code>audit:read</code>.
          </div>

          <div style={{ maxHeight: 420, overflow: "auto" }}>
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

          <button className="btn" style={{ marginTop: 10 }} onClick={refresh}>
            Refresh
          </button>
        </section>
      </div>
    </div>
  );
}
