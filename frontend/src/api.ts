/**
 * Datei: frontend/src/api.ts
 *
 * Zweck:
 * - Enthält UI-/Client-Logik dieser Anwendung.
 * - Kommentare wurden ergänzt, um Einstieg und Wartung zu erleichtern.
 *
 * Hinweis:
 * - Kommentare erklären Struktur/Intention; die fachliche Wahrheit kommt aus Backend/API-Verträgen.
 */

import type { CaseSummary, CaseDetail } from "./types";

export async function fetchCases(): Promise<CaseSummary[]> {
  const res = await fetch("/api/cases");
  if (!res.ok) {
    throw new Error(`Failed to fetch cases: ${res.status}`);
  }
  return res.json();
}

export async function fetchCaseDetail(caseId: string): Promise<CaseDetail> {
  const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch case detail: ${res.status}`);
  }
  return res.json();
}

export async function ackCase(caseId: string): Promise<{ case_id: string; acked_at: string }> {
  const res = await fetch(`/api/ack/${encodeURIComponent(caseId)}`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to ack case: ${res.status}`);
  return res.json();
}

export async function unackCase(caseId: string): Promise<{ case_id: string; acked_at: null }> {
  const res = await fetch(`/api/unack/${encodeURIComponent(caseId)}`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to unack case: ${res.status}`);
  return res.json();
}
