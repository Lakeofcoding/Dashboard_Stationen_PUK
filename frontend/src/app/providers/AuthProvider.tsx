/**
 * AuthProvider (Frontend).
 *
 * Ziel:
 * - Station/User/Rollen nur an einer Stelle verwalten
 * - Seiten (Checks/Monitoring/...) greifen über Context darauf zu
 *
 * IMPORTANT:
 * In Produktion darf das Frontend keine Rollen "erfinden".
 * Der Demo-Modus ist nur für lokale Tests.
 */

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { DEMO_AUTH_ENABLED, loadAuth, saveAuth, parseRoles } from "../../shared/auth/auth";
import type { AuthState } from "../../shared/auth/auth";

type MetaUser = { user_id: string; roles: string[] };

type AuthContextValue = {
  demoEnabled: boolean;
  auth: AuthState;
  setAuthPatch: (patch: Partial<AuthState>) => void;
  roles: Set<string>;
  canAck: boolean;
  stations: string[];
  metaUsers: MetaUser[];
  metaError: string | null;
};

const Ctx = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [auth, setAuth] = useState<AuthState>(() => loadAuth());

  // Meta-Daten (optional): Stationen & definierte Benutzer aus dem Backend
  const [stations, setStations] = useState<string[]>(["A1", "B0", "B2"]);
  const [metaUsers, setMetaUsers] = useState<MetaUser[]>([
    { user_id: "demo", roles: ["VIEW_DASHBOARD", "ACK_ALERT"] },
    { user_id: "pflege1", roles: ["VIEW_DASHBOARD"] },
    { user_id: "arzt1", roles: ["VIEW_DASHBOARD", "ACK_ALERT"] },
  ]);
  const [metaError, setMetaError] = useState<string | null>(null);

  function setAuthPatch(patch: Partial<AuthState>) {
    setAuth((prev) => {
      const next = { ...prev, ...patch };
      saveAuth(next);
      return next;
    });
  }

  const roles = useMemo(() => parseRoles(auth.rolesCsv), [auth.rolesCsv]);
  const canAck = roles.has("ACK_ALERT");

  // Meta endpoints (optional). In Produktion ist das Backend "source of truth".
  useEffect(() => {
    if (!DEMO_AUTH_ENABLED) return;

    let alive = true;

    (async () => {
      try {
        const st = await fetch("/api/meta/stations").then((r) =>
          r.ok ? r.json() : Promise.reject(new Error("meta/stations"))
        );
        if (alive && Array.isArray(st?.stations) && st.stations.length) {
          setStations(st.stations);
          if (!st.stations.includes(auth.stationId)) {
            setAuthPatch({ stationId: st.stations[0] });
          }
        }
      } catch {
        // optional
      }

      try {
        const us = await fetch("/api/meta/users").then((r) =>
          r.ok ? r.json() : Promise.reject(new Error("meta/users"))
        );
        if (alive && Array.isArray(us?.users) && us.users.length) {
          setMetaUsers(us.users);
          const u = us.users.find((x: MetaUser) => x.user_id === auth.userId) ?? us.users[0];
          if (u) setAuthPatch({ userId: u.user_id, rolesCsv: (u.roles ?? []).join(",") });
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

  // Rollen im Demo-Modus nur aus Meta ableiten (kein Freitext), falls vorhanden.
  useEffect(() => {
    if (!DEMO_AUTH_ENABLED) return;
    const u = metaUsers.find((x) => x.user_id === auth.userId);
    if (u) {
      const next = (u.roles ?? []).join(",");
      if (next && next !== auth.rolesCsv) setAuthPatch({ rolesCsv: next });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.userId, metaUsers]);

  const value: AuthContextValue = {
    demoEnabled: DEMO_AUTH_ENABLED,
    auth,
    setAuthPatch,
    roles,
    canAck,
    stations,
    metaUsers,
    metaError,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth muss innerhalb von <AuthProvider> verwendet werden.");
  return v;
}
