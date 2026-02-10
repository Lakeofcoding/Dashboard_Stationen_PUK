/**
 * Auth-/Kontext-Handling (Frontend).
 *
 * WICHTIG: Ein Browser ist niemals eine Vertrauensgrenze.
 * In Produktion dürfen Rollen/Rechte NICHT vom Client kommen.
 *
 * Dieses Projekt enthält einen Demo-Modus für lokale Entwicklung:
 * - Station, User und Rollen werden im localStorage gespeichert.
 * - Die Werte werden als HTTP-Header an das Backend gesendet.
 *
 * In der echten Intranet-Installation muss das anders laufen:
 * - Authentifizierung via SSO/Reverse-Proxy
 * - Rollen kommen aus dem Backend/Directory
 * - Der Browser sendet keine "Rollen-Header" nach Belieben
 */

export type AuthState = {
  stationId: string;
  userId: string;
  rolesCsv: string; // z.B. "VIEW_DASHBOARD,ACK_ALERT" (nur Demo)
};

// Demo-Schalter: in Produktion auf 0 lassen.
// In Vite kannst du .env.local setzen: VITE_DEMO_AUTH=1
export const DEMO_AUTH_ENABLED = import.meta.env.VITE_DEMO_AUTH === "1";

const LS_KEYS = {
  stationId: "dashboard.stationId",
  userId: "dashboard.userId",
  rolesCsv: "dashboard.rolesCsv",
};

export function loadAuth(): AuthState {
  // Für Demo/Entwicklung benutzen wir localStorage.
  // Wenn DEMO_AUTH_ENABLED=false, liefern wir "leere" Werte zurück.
  if (!DEMO_AUTH_ENABLED) {
    return { stationId: "", userId: "", rolesCsv: "" };
  }

  return {
    stationId: localStorage.getItem(LS_KEYS.stationId) ?? "B0",
    userId: localStorage.getItem(LS_KEYS.userId) ?? "demo",
    rolesCsv: localStorage.getItem(LS_KEYS.rolesCsv) ?? "VIEW_DASHBOARD,ACK_ALERT",
  };
}

export function saveAuth(a: AuthState) {
  if (!DEMO_AUTH_ENABLED) return;
  localStorage.setItem(LS_KEYS.stationId, a.stationId);
  localStorage.setItem(LS_KEYS.userId, a.userId);
  localStorage.setItem(LS_KEYS.rolesCsv, a.rolesCsv);
}

export function parseRoles(csv: string): Set<string> {
  return new Set(
    csv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );
}

/**
 * authHeaders: Header, die wir beim Aufruf an das Backend mitsenden.
 *
 * In Produktion sollte hier nichts "frei editierbares" mehr stehen.
 */
export function authHeaders(auth: AuthState): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (DEMO_AUTH_ENABLED) {
    headers["X-Station-Id"] = auth.stationId;
    headers["X-User-Id"] = auth.userId;
    headers["X-Roles"] = auth.rolesCsv;
  }

  return headers;
}
