/**
 * Datei: frontend/vite.config.ts
 *
 * Zweck:
 * - Enthält UI-/Client-Logik dieser Anwendung.
 * - Kommentare wurden ergänzt, um Einstieg und Wartung zu erleichtern.
 *
 * Hinweis:
 * - Kommentare erklären Struktur/Intention; die fachliche Wahrheit kommt aus Backend/API-Verträgen.
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
