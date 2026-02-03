import type { CaseSummary } from "./types";

export async function fetchCases(): Promise<CaseSummary[]> {
  const res = await fetch("/api/cases");
  if (!res.ok) {
    throw new Error(`Failed to fetch cases: ${res.status}`);
  }
  return res.json();
}
