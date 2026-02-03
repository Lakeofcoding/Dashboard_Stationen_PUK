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
