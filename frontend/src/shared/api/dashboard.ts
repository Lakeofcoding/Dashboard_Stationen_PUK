/**
 * API-Funktionen für das Dashboard.
 *
 * Hier konzentrieren wir alle Endpoints, die mehrere Seiten nutzen.
 */

import type { CaseDetail, CaseSummary } from "../../types";
import { fetchJson } from "./client";
import { authHeaders } from "../auth/auth";
import type { AuthState } from "../auth/auth";

export async function fetchCases(auth: AuthState): Promise<CaseSummary[]> {
  return fetchJson<CaseSummary[]>("/api/cases", {
    method: "GET",
    headers: authHeaders(auth),
  });
}

export async function fetchCaseDetail(caseId: string, auth: AuthState): Promise<CaseDetail> {
  return fetchJson<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`, {
    method: "GET",
    headers: authHeaders(auth),
  });
}

export async function ackCase(caseId: string, auth: AuthState): Promise<{ acked_at: string }> {
  return fetchJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, ack_scope: "case", scope_id: "*" }),
  });
}

export async function ackRule(caseId: string, ruleId: string, auth: AuthState): Promise<{ acked_at: string }> {
  return fetchJson<{ acked_at: string }>("/api/ack", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, ack_scope: "rule", scope_id: ruleId }),
  });
}

/**
 * "Schieben" eines Falls: wir protokollieren, warum der Fall zurückgestellt wurde.
 *
 * Hinweis:
 * - In einer echten KISIM-Integration würde man hier vermutlich Statusfelder im System setzen.
 * - Für das MVP speichern wir eine "defer"-Info pro Fall/Station.
 */
export async function deferCase(
  caseId: string,
  reason: string,
  auth: AuthState
): Promise<{ deferred_at: string }> {
  return fetchJson<{ deferred_at: string }>("/api/defer", {
    method: "POST",
    headers: authHeaders(auth),
    body: JSON.stringify({ case_id: caseId, reason }),
  });
}
