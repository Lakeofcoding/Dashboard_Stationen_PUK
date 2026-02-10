/**
 * Seite: Fallinformationen
 *
 * Zweck:
 * - Übersicht über Fall-/Patienteninformationen (ohne den Fokus auf die Regelalarme)
 * - Im MVP nutzen wir dieselben API-Endpunkte wie die Vollständigkeitsseite.
 *
 * Hinweis zu PHI/Patientendaten:
 * - Dieses UI zeigt aktuell im Demo-Datensatz eine patient_id.
 * - In echten Umgebungen: Datenminimierung beachten (nur anzeigen, was für die Aufgabe nötig ist).
 */

import { useEffect, useMemo, useState } from "react";
import type { CaseDetail, CaseSummary } from "../types";
import { fetchCases, fetchCaseDetail, ackCase, deferCase } from "../shared/api/dashboard";
import { useAuth } from "../app/providers/AuthProvider";
import { Button } from "../shared/ui/Button";
import { Modal } from "../shared/ui/Modal";
import { Toast } from "../Toast";

type ToastState =
  | { caseId: string; message: string; kind: "critical" | "warn" | "info" }
  | null;

function formatMaybe(v: any) {
  return v === null || v === undefined || v === "" ? "-" : String(v);
}

export function FallinformationenPage() {
  const { demoEnabled, auth, setAuthPatch, canAck, stations, metaUsers, metaError } = useAuth();

  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [toast, setToast] = useState<ToastState>(null);

  // "Schieben" Modal
  const [deferOpen, setDeferOpen] = useState(false);
  const [deferReason, setDeferReason] = useState<string>("Grund A (z.B. Rückfrage nötig)");

  const deferReasons = useMemo(
    () => [
      "Grund A (z.B. Rückfrage nötig)",
      "Grund B (z.B. Daten fehlen / KISIM Nachtrag)",
      "Grund C (z.B. Verantwortlichkeit unklar)",
    ],
    []
  );

  // Liste laden (in dieser Ansicht genügt langsameres Polling)
  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const data = await fetchCases(auth);
        if (!alive) return;
        setCases(data);
        setError(null);
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message ?? String(e));
      }
    };

    load();
    const id = window.setInterval(load, 20_000);
    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [auth.stationId, auth.userId, auth.rolesCsv]);

  // Details laden
  useEffect(() => {
    if (!selectedCaseId) {
      setDetail(null);
      setDetailError(null);
      return;
    }

    let alive = true;
    setDetailLoading(true);

    (async () => {
      try {
        const d = await fetchCaseDetail(selectedCaseId, auth);
        if (!alive) return;
        setDetail(d);
        setDetailError(null);
      } catch (e: any) {
        if (!alive) return;
        setDetail(null);
        setDetailError(e?.message ?? String(e));
      } finally {
        if (alive) setDetailLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [selectedCaseId, auth.stationId, auth.userId, auth.rolesCsv]);

  const selectedSummary = useMemo(
    () => cases.find((c) => c.case_id === selectedCaseId) ?? null,
    [cases, selectedCaseId]
  );

  async function onAckCase() {
    if (!selectedCaseId) return;
    try {
      await ackCase(selectedCaseId, auth);
      const d = await fetchCaseDetail(selectedCaseId, auth);
      setDetail(d);
      setToast({ kind: "info", caseId: selectedCaseId, message: `${selectedCaseId} quittiert` });
    } catch (e: any) {
      setToast({ kind: "warn", caseId: selectedCaseId, message: e?.message ?? String(e) });
    }
  }

  async function onDeferCase() {
    if (!selectedCaseId) return;
    try {
      await deferCase(selectedCaseId, deferReason, auth);
      const d = await fetchCaseDetail(selectedCaseId, auth);
      setDetail(d);
      setToast({ kind: "info", caseId: selectedCaseId, message: `${selectedCaseId} geschoben: ${deferReason}` });
    } catch (e: any) {
      setToast({ kind: "warn", caseId: selectedCaseId, message: e?.message ?? String(e) });
    } finally {
      setDeferOpen(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[380px_1fr]">
      {/* Sidebar */}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Fallinformationen</h2>
          {demoEnabled ? (
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-700">Demo-Modus</span>
          ) : (
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">Intranet/SSO</span>
          )}
        </div>

        {metaError ? <p className="mt-2 text-xs text-amber-700">{metaError}</p> : null}

        {demoEnabled ? (
          <div className="mt-3 grid gap-2">
            <label className="text-xs text-slate-600">
              Station
              <select
                className="mt-1 w-full rounded-md border border-slate-200 bg-white p-2 text-sm"
                value={auth.stationId}
                onChange={(e) => setAuthPatch({ stationId: e.target.value })}
              >
                {stations.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>

            <label className="text-xs text-slate-600">
              Benutzer
              <select
                className="mt-1 w-full rounded-md border border-slate-200 bg-white p-2 text-sm"
                value={auth.userId}
                onChange={(e) => setAuthPatch({ userId: e.target.value })}
              >
                {metaUsers.map((u) => (
                  <option key={u.user_id} value={u.user_id}>
                    {u.user_id}
                  </option>
                ))}
              </select>
            </label>

            <div className="text-xs text-slate-600">
              Rollen: <span className="font-mono">{auth.rolesCsv || "-"}</span>
            </div>
          </div>
        ) : (
          <p className="mt-3 text-xs text-slate-600">
            Produktion: Station/Benutzer kommen aus SSO/Proxy. Keine Eingabe im Frontend.
          </p>
        )}

        {error ? <p className="mt-3 text-sm text-red-700">Fehler: {error}</p> : null}

        <div className="mt-3">
          <h3 className="text-xs font-semibold text-slate-700">Fälle</h3>
          <div className="mt-2 max-h-[520px] overflow-auto rounded-lg border border-slate-100">
            {cases.map((c) => (
              <button
                key={c.case_id}
                className={
                  "flex w-full items-center justify-between gap-3 border-b border-slate-100 p-3 text-left hover:bg-slate-50 " +
                  (c.case_id === selectedCaseId ? "bg-slate-50" : "bg-white")
                }
                onClick={() => setSelectedCaseId(c.case_id)}
              >
                <div>
                  <div className="text-sm font-medium">{c.case_id}</div>
                  <div className="text-xs text-slate-600">Patient: {c.patient_id ?? "-"}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    Eintritt: {String(c.admission_date)}
                    {c.discharge_date ? ` · Austritt: ${String(c.discharge_date)}` : ""}
                  </div>
                </div>

                <div className="flex flex-col items-end gap-1">
                  {c.acked_at ? (
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-700">quittiert</span>
                  ) : null}
                  {c.deferred_at ? (
                    <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] text-amber-800">geschoben</span>
                  ) : null}
                </div>
              </button>
            ))}
            {cases.length === 0 ? <div className="p-3 text-sm text-slate-600">Keine Fälle gefunden.</div> : null}
          </div>
        </div>
      </section>

      {/* Detail */}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold">Details</h2>

        {!selectedCaseId ? <p className="mt-3 text-sm text-slate-600">Wähle links einen Fall.</p> : null}
        {detailLoading ? <p className="mt-3 text-sm text-slate-600">Lade...</p> : null}
        {detailError ? <p className="mt-3 text-sm text-red-700">Fehler: {detailError}</p> : null}

        {selectedSummary ? (
          <div className="mt-3 grid gap-3">
            <div className="grid grid-cols-1 gap-2 rounded-xl border border-slate-100 bg-slate-50 p-4 sm:grid-cols-2">
              <div>
                <div className="text-xs text-slate-500">Fall</div>
                <div className="font-mono text-sm">{selectedSummary.case_id}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Station</div>
                <div className="text-sm">{selectedSummary.station_id}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Eintritt</div>
                <div className="text-sm">{formatMaybe(selectedSummary.admission_date)}</div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Austritt</div>
                <div className="text-sm">{formatMaybe(selectedSummary.discharge_date)}</div>
              </div>
            </div>

            {detail ? (
              <div className="grid gap-3">
                <div className="grid grid-cols-1 gap-2 rounded-xl border border-slate-100 p-4 sm:grid-cols-3">
                  <div>
                    <div className="text-xs text-slate-500">HONOS (Eintritt)</div>
                    <div className="text-sm font-semibold">{formatMaybe(detail.honos)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">BSCL (Eintritt)</div>
                    <div className="text-sm font-semibold">{formatMaybe(detail.bscl)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-slate-500">BFS vollständig</div>
                    <div className="text-sm font-semibold">{detail.bfs_complete ? "ja" : "nein"}</div>
                  </div>
                </div>

                <div className="grid gap-1 text-xs text-slate-600">
                  <div>
                    Fall quittiert: <span className="font-mono">{detail.acked_at ? detail.acked_at : "nein"}</span>
                  </div>
                  <div>
                    Fall geschoben: <span className="font-mono">{detail.deferred_at ? detail.deferred_at : "nein"}</span>
                    {detail.deferred_reason ? <span className="ml-2 text-slate-500">({detail.deferred_reason})</span> : null}
                  </div>
                </div>

                {canAck ? (
                  <div className="mt-2 flex items-center justify-end gap-2">
                    <Button variant="secondary" onClick={() => setDeferOpen(true)}>
                      Schieben
                    </Button>
                    <Button variant="primary" onClick={onAckCase}>
                      Fall quittieren
                    </Button>
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}
      </section>

      <Modal open={deferOpen} title={`Fall ${selectedCaseId ?? ""} schieben`} onClose={() => setDeferOpen(false)}>
        <div className="grid gap-3">
          <div className="grid gap-2">
            {deferReasons.map((r) => (
              <label
                key={r}
                className={
                  "flex cursor-pointer items-start gap-3 rounded-lg border p-3 " +
                  (deferReason === r ? "border-slate-300 bg-slate-50" : "border-slate-100 bg-white")
                }
              >
                <input
                  type="radio"
                  name="defer-reason"
                  value={r}
                  checked={deferReason === r}
                  onChange={() => setDeferReason(r)}
                  className="mt-1"
                />
                <div>
                  <div className="text-sm font-medium">{r}</div>
                  <div className="mt-1 text-xs text-slate-600">
                    Hinweis: Gründe sind im MVP fix. Später kann man eine zentrale Liste pflegen.
                  </div>
                </div>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeferOpen(false)}>
              Abbrechen
            </Button>
            <Button variant="primary" onClick={onDeferCase} disabled={!selectedCaseId}>
              Schieben bestätigen
            </Button>
          </div>
        </div>
      </Modal>

      {toast ? <Toast kind={toast.kind} message={toast.message} onClose={() => setToast(null)} /> : null}
    </div>
  );
}
