export type Severity = "OK" | "WARN" | "CRITICAL";

export interface Alert {
  rule_id: string;
  severity: Severity;
  message: string;
  explanation: string;
  condition_hash?: string;
}

export interface CaseSummary {
  case_id: string;
  // Optional: Das Backend liefert patient_id (im Demo-Datensatz). Für echte PHI gilt Datenminimierung.
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

  // "Schieben"-Info (MVP): letzter Schiebegrund + Zeitpunkt
  deferred_at?: string | null;
  deferred_reason?: string | null;
}

export interface CaseDetail extends CaseSummary {
  honos?: number | null;
  bscl?: number | null;
  bfs_complete: boolean;
  alerts: Alert[];
  rule_acks: Record<string, string>; // rule_id -> acked_at
}
