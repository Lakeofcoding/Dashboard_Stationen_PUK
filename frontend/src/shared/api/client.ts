/**
 * Zentrale API-Hilfsfunktionen.
 *
 * Warum überhaupt ein "API-Client"?
 * - Damit alle Seiten gleich reagieren (Loading/Fehler/JSON-Parsing).
 * - Damit wir an einer Stelle später Security-Header, Correlation-IDs usw. ergänzen können.
 *
 * Wichtig für Intranet/Patientendaten:
 * - Keine externen URLs. Wir verwenden nur relative Pfade wie "/api/...".
 */

export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * fetchJson lädt JSON von unserem Backend.
 *
 * - Wir prüfen absichtlich den Content-Type, um Konfigurationsfehler sichtbar zu machen
 *   (z.B. wenn ein Proxy statt JSON HTML liefert).
 */
export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      ...(init?.headers ?? {}),
    },
  });

  const contentType = res.headers.get("content-type") ?? "";

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `HTTP ${res.status}`);
  }

  if (!contentType.includes("application/json")) {
    const text = await res.text().catch(() => "");
    throw new ApiError(
      500,
      `Backend lieferte kein JSON (Content-Type: ${contentType}). Anfang: ${text.slice(0, 80)}`
    );
  }

  return (await res.json()) as T;
}
