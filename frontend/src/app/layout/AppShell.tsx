/**
 * AppShell ist das "Gerüst" der Anwendung:
 * - Kopfzeile
 * - Navigation (Reiter)
 * - Platzhalter für die aktuell gewählte Seite (<Outlet />)
 */

import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useMemo } from "react";

const navLinkClassName = ({ isActive }: { isActive: boolean }) =>
  [
    "px-3 py-2 rounded-md text-sm",
    isActive
      ? "bg-slate-900 text-white"
      : "bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50",
  ].join(" ");

/**
 * Kleiner Helper: wir erlauben optional eine Station in der URL als Query, z.B.:
 *   /checks?station=B0
 *
 * Das ist später praktisch, wenn du Links zu einer bestimmten Station verschicken willst.
 */
function useStationQueryParam() {
  const location = useLocation();
  const navigate = useNavigate();

  const stationId = useMemo(() => {
    const p = new URLSearchParams(location.search);
    return p.get("station") ?? "";
  }, [location.search]);

  function setStationId(next: string) {
    const p = new URLSearchParams(location.search);
    if (next) p.set("station", next);
    else p.delete("station");
    navigate({ pathname: location.pathname, search: p.toString() });
  }

  return { stationId, setStationId };
}

export function AppShell() {
  // Branding-Placeholder (wie von dir gewünscht)
  const clinicName = "Psychiatrische Universitätsklinik Zürich";

  // Nur damit die Seiten eine Station via URL lesen können, falls gesetzt.
  // (Die Seiten können auch eigene Station-Logik haben.)
  const { stationId } = useStationQueryParam();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto max-w-6xl px-4 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold">Dashboard</h1>
              <p className="text-xs text-slate-600">{clinicName}</p>
            </div>

            {/* Anzeige nur zur Orientierung (kommt später aus SSO) */}
            {stationId ? (
              <div className="text-xs text-slate-600">Station (URL): {stationId}</div>
            ) : null}
          </div>

          <nav className="mt-4 flex gap-2">
            <NavLink to="/checks" className={navLinkClassName}>
              Vollständigkeit
            </NavLink>
            <NavLink to="/fallinformationen" className={navLinkClassName}>
              Fallinformationen
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
