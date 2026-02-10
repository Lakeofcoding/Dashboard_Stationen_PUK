/**
 * Router-Konfiguration.
 *
 * Wir nutzen "Routen" statt reinem UI-State (Tabs), weil:
 * - URLs sind teilbar (Deep Links)
 * - Browser-Back/Forward funktioniert
 * - Später können Rechte pro Route geprüft werden
 */

import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { ChecksPage } from "../pages/ChecksPage";
import { FallinformationenPage } from "../pages/FallinformationenPage";
import { NotFoundPage } from "../pages/NotFoundPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      // Startseite: Vollständigkeitskontrollen
      { index: true, element: <ChecksPage /> },
      { path: "checks", element: <ChecksPage /> },
      { path: "fallinformationen", element: <FallinformationenPage /> },

      // Fallback
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
