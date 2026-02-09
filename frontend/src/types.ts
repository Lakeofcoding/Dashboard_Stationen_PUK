export type Severity = "OK" | "WARN" | "CRITICAL";

export interface CaseSummary {
  case_id: string;
  station_id: string;
  admission_date: string;
  discharge_date: string | null;
  severity: Severity;
  top_alert: string | null;
  acked_at: string | null; // <-- wichtig
}

export interface Alert {
  rule_id: string;
  severity: Severity;
  message: string;
  explanation: string;
}

export interface CaseDetail extends CaseSummary {
  honos: number | null;
  bscl: number | null;
  bfs_complete: boolean;
  alerts: Alert[];
}
