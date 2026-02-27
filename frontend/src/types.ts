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
  // Alert-Mapping (v5)
  rule_id?: string | null;
  explanation?: string | null;
  condition_hash?: string | null;
  // ACK/SHIFT status (injected by router)
  ack?: { state: "ACK" | "SHIFT"; ts: string; shift_code?: string | null } | null;
}

export interface ParameterGroup {
  key: string;
  label: string;
  severity: Severity;
  items: ParameterStatus[];
}

export interface LangliegerStatus {
  active: boolean;
  severity: Severity;
  days: number;
  week?: number | null;
  message?: string | null;
  next_threshold?: number | null;
}

export interface FuStatus {
  is_fu: boolean;
  fu_typ?: string | null;
  fu_datum?: string | null;
  fu_gueltig_bis?: string | null;
  days_until_expiry?: number | null;
  severity: Severity;
  message?: string | null;
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
  // Per-category severity
  completeness_severity?: Severity;
  completeness_critical?: number;
  completeness_warn?: number;
  medical_severity?: Severity;
  medical_critical?: number;
  medical_warn?: number;
  // Fallstatus & Verantwortlichkeit
  case_status?: string | null;
  responsible_person?: string | null;
  acked_at?: string | null;
  parameter_status?: ParameterStatus[];
  // ACK-Fortschritt
  total_alerts?: number;
  open_alerts?: number;
  acked_alerts?: number;
  last_ack_by?: string | null;
  last_ack_at?: string | null;
  // v4
  days_since_admission?: number;
  langlieger?: LangliegerStatus | null;
}

export interface CaseDetail extends CaseSummary {
  honos?: number | null;
  bscl?: number | null;
  bfs_complete: boolean;
  alerts: Alert[];
  // rule_id -> Status der Einzelmeldung für *heute*
  rule_states: Record<string, { state: "ACK" | "SHIFT"; ts: string; shift_code?: "a" | "b" | "c" | null }>;
  // v4: Hierarchische Parametergruppen + FU
  parameter_groups?: ParameterGroup[];
  fu_status?: FuStatus | null;
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
