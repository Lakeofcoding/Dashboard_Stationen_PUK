/**
 * App ist jetzt nur noch der Einstiegspunkt:
 * - RouterProvider: steuert die Seiten (Routes)
 * - AuthProvider: hält Demo-Kontext (Station/User/Rollen) für alle Seiten bereit
 */

import { RouterProvider } from "react-router-dom";
import { router } from "./app/router";
import { AuthProvider } from "./app/providers/AuthProvider";

export default function App() {
  return (
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  );
}
