/**
 * Datei: frontend/src/types.ts
 *
 * Zweck:
 * - Enthält UI-/Client-Logik dieser Anwendung.
 * - Kommentare wurden ergänzt, um Einstieg und Wartung zu erleichtern.
 *
 * Hinweis:
 * - Kommentare erklären Struktur/Intention; die fachliche Wahrheit kommt aus Backend/API-Verträgen.
 */

export type Severity = "OK" | "WARN" | "CRITICAL";

export interface Alert {
  rule_id: string;
  severity: Severity;
  category: "completeness" | "medical";
  message: string;
  explanation: string;
  condition_hash?: string;
}

export interface ParameterStatus {
  id: string;
  label: string;
  group: "completeness" | "medical";
  status: "ok" | "warn" | "critical" | "na";
  detail: string | null;
}

export interface CaseSummary {
  case_id: string;
  patient_id?: string;
  clinic?: string;
  center?: string;
  station_id: string;
  admission_date: string;
  discharge_date: string | null;
  severity: Severity;
  top_alert?: string | null;
  critical_count?: number;
  warn_count?: number;
  acked_at?: string | null;
  parameter_status?: ParameterStatus[];
}

export interface CaseDetail extends CaseSummary {
  honos?: number | null;
  bscl?: number | null;
  bfs_complete: boolean;
  alerts: Alert[];
  // rule_id -> Status der Einzelmeldung für *heute*
  rule_states: Record<string, { state: "ACK" | "SHIFT"; ts: string; shift_code?: "a" | "b" | "c" | null }>;
}

export interface DayState {
  station_id: string;
  business_date: string; // YYYY-MM-DD
  version: number; // "Vers" pro Tag
}
