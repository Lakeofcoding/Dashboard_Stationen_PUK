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

// ─── Longitudinal data for charts ───

export interface LabMeasurement {
  date: string;
  week: number | null;
  leuko: number | null;
  neutro: number | null;
  neutro_pct: number | null;
  ery: number | null;
  hb: number | null;
  thrombo: number | null;
  cloz_spiegel: number | null;
  norclozapin: number | null;
  troponin: number | null;
  glukose: number | null;
  hba1c: number | null;
  cholesterin: number | null;
  triglyzeride: number | null;
  alat: number | null;
  asat: number | null;
  crp: number | null;
  bemerkung: string | null;
}

export interface EkgMeasurement {
  date: string;
  typ: string | null;
  hr: number | null;
  qtc: number | null;
  qtc_method: string | null;
  pq: number | null;
  qrs: number | null;
  rhythmus: string | null;
  befund: string | null;
  befundet_durch: string | null;
  befunddatum_str: string | null;
  bemerkung: string | null;
}

export interface EfmEvent {
  code: number | null;
  name: string | null;
  group: string | null;
  start: string;
  end_str: string | null;
  duration_min: number | null;
  angeordnet_durch: string | null;
}
