/**
 * Seite: Vollständigkeitskontrollen
 *
 * Diese Seite entspricht funktional der früheren "App.tsx"-Monolith-Komponente,
 * ist aber jetzt als eigene Route umgesetzt.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import type { CaseDetail, CaseSummary, Severity } from "../types";
import { Toast } from "../Toast";
import { fetchCases, fetchCaseDetail, ackCase, ackRule, deferCase } from "../shared/api/dashboard";
import { useAuth } from "../app/providers/AuthProvider";
import { Button } from "../shared/ui/Button";
import { Modal } from "../shared/ui/Modal";

type ToastState =
  | { caseId: string; message: string; kind: "critical" | "warn" | "info" }
  | null;

function severityPill(sev: Severity) {
  if (sev === "CRITICAL") return "bg-red-50 text-red-700 ring-1 ring-red-100";
  if (sev === "WARN") return "bg-amber-50 text-amber-800 ring-1 ring-amber-100";
  return "bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100";
}

export function ChecksPage() {
  const { demoEnabled, auth, setAuthPatch, canAck, stations, metaUsers, metaError } = useAuth();

  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [toast, setToast] = useState<ToastState>(null);
  const shownCriticalRef = useRef<Record<string, true>>({});

  // "Schieben" (Defer) Modal-UI-State
  const [deferOpen, setDeferOpen] = useState(false);
  const [deferReason, setDeferReason] = useState<string>("Grund A (z.B. Rückfrage nötig)");

  // Gründe (MVP). Später kann das aus einer Konfiguration oder aus dem Backend kommen.
  const deferReasons = useMemo(
    () => [
      "Grund A (z.B. Rückfrage nötig)",
      "Grund B (z.B. Daten fehlen / KISIM Nachtrag)",
      "Grund C (z.B. Verantwortlichkeit unklar)",
    ],
    []
  );

  // Polling für die Fallliste (Vollständigkeitskontrollen ändern sich nicht sekündlich;
  // daher reicht ein moderates Intervall).
  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const data = await fetchCases(auth);
        if (!alive) return;
        setCases(data);
        setError(null);

        // Einfache Toast-Logik: zeige einmalig den ersten neuen CRITICAL-Fall.
        if (!toast) {
          const firstCritical = data.find(
            (c) =>
              (c.critical_count ?? (c.severity === "CRITICAL" ? 1 : 0)) > 0 &&
              !shownCriticalRef.current[c.case_id]
          );
          if (firstCritical) {
            setToast({
              kind: "critical",
              caseId: firstCritical.case_id,
              message: `${firstCritical.case_id}: ${firstCritical.top_alert ?? "Kritischer Status"}`,
            });
            shownCriticalRef.current[firstCritical.case_id] = true;
          }
        }
      } catch (e: any) {
        if (!alive) return;
        setError(e?.message ?? String(e));
      }
    };

    load();
    const id = window.setInterval(load, 15_000);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.stationId, auth.userId, auth.rolesCsv]);

  // Detail laden, wenn ein Fall ausgewählt wird.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCaseId, auth.stationId, auth.userId, auth.rolesCsv]);

  const selectedSummary = useMemo(
    () => cases.find((c) => c.case_id === selectedCaseId) ?? null,
    [cases, selectedCaseId]
  );

  async function onAckCase() {
    if (!selectedCaseId) return;
    try {
      await ackCase(selectedCaseId, auth);
      // Nach Quittierung: Details neu laden und Liste refresht automatisch im nächsten Poll.
      const d = await fetchCaseDetail(selectedCaseId, auth);
      setDetail(d);
      setToast({ kind: "info", caseId: selectedCaseId, message: `${selectedCaseId} quittiert` });
    } catch (e: any) {
      setToast({ kind: "warn", caseId: selectedCaseId, message: e?.message ?? String(e) });
    }
  }

  async function onAckRule(ruleId: string) {
    if (!selectedCaseId) return;
    try {
      await ackRule(selectedCaseId, ruleId, auth);
      const d = await fetchCaseDetail(selectedCaseId, auth);
      setDetail(d);
      setToast({ kind: "info", caseId: selectedCaseId, message: `Regel ${ruleId} quittiert` });
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
      {/* Sidebar: Kontext + Liste */}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Vollständigkeit</h2>
          {demoEnabled ? (
            <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] text-slate-700">
              Demo-Modus
            </span>
          ) : (
            <span className="rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700">
              Intranet/SSO
            </span>
          )}
        </div>

        {metaError ? <p className="mt-2 text-xs text-amber-700">{metaError}</p> : null}

        {/* Diese Auswahl ist nur für Demo/Entwicklung gedacht. */}
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
              Rollen (aus Backend-Meta): <span className="font-mono">{auth.rolesCsv || "-"}</span>
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
                  <span className={"rounded-full px-2 py-1 text-[11px] " + severityPill(c.severity)}>
                    {c.severity}
                  </span>
                  {c.deferred_at ? (
                    <span className="rounded-full bg-amber-50 px-2 py-1 text-[11px] text-amber-800">
                      geschoben
                    </span>
                  ) : null}
                  {(c.critical_count ?? 0) > 0 ? (
                    <span className="text-[11px] text-red-700">kritisch: {c.critical_count}</span>
                  ) : null}
                  {(c.warn_count ?? 0) > 0 ? (
                    <span className="text-[11px] text-amber-700">warn: {c.warn_count}</span>
                  ) : null}
                </div>
              </button>
            ))}
            {cases.length === 0 ? (
              <div className="p-3 text-sm text-slate-600">Keine Fälle gefunden.</div>
            ) : null}
          </div>
        </div>
      </section>

      {/* Detail */}
      <section className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <h2 className="text-sm font-semibold">Details</h2>

        {!selectedCaseId ? (
          <p className="mt-3 text-sm text-slate-600">Wähle links einen Fall.</p>
        ) : null}

        {detailLoading ? <p className="mt-3 text-sm text-slate-600">Lade...</p> : null}
        {detailError ? <p className="mt-3 text-sm text-red-700">Fehler: {detailError}</p> : null}

        {selectedSummary ? (
          <div className="mt-3 grid gap-2 text-sm">
            <div>
              <span className="text-slate-500">Fall:</span> <span className="font-mono">{selectedSummary.case_id}</span>
            </div>
            <div>
              <span className="text-slate-500">Station:</span> {selectedSummary.station_id}
            </div>
            <div>
              <span className="text-slate-500">Status:</span> {selectedSummary.severity}
            </div>
          </div>
        ) : null}

        {detail ? (
          <div className="mt-4">
            <h3 className="text-xs font-semibold text-slate-700">Alarme</h3>
            <div className="mt-2 grid gap-2">
              {detail.alerts.map((a) => {
                const isAcked = Boolean(detail.rule_acks?.[a.rule_id]);
                return (
                  <div key={a.rule_id} className="rounded-lg border border-slate-100 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium">{a.message}</div>
                        <div className="mt-1 text-xs text-slate-600">{a.explanation}</div>
                        <div className="mt-1 text-[11px] text-slate-400">Regel: {a.rule_id}</div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={"rounded-full px-2 py-1 text-[11px] " + severityPill(a.severity)}>
                          {a.severity}
                        </span>
                        {canAck ? (
                          <Button
                            size="sm"
                            variant={isAcked ? "ghost" : "secondary"}
                            disabled={isAcked}
                            onClick={() => onAckRule(a.rule_id)}
                          >
                            {isAcked ? "Quittiert" : "Quittieren"}
                          </Button>
                        ) : (
                          <div className="text-[11px] text-slate-500">Keine Quittierrechte</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
              {detail.alerts.length === 0 ? (
                <div className="text-sm text-slate-600">Keine aktiven Alarme.</div>
              ) : null}
            </div>

            <div className="mt-4 flex items-center justify-between">
              <div className="text-xs text-slate-600 grid gap-1">
                <div>
                  Fall quittiert: <span className="font-mono">{detail.acked_at ? detail.acked_at : "nein"}</span>
                </div>
                <div>
                  Fall geschoben: <span className="font-mono">{detail.deferred_at ? detail.deferred_at : "nein"}</span>
                  {detail.deferred_reason ? (
                    <span className="ml-2 text-slate-500">({detail.deferred_reason})</span>
                  ) : null}
                </div>
              </div>

              {canAck ? (
                <div className="flex items-center gap-2">
                  <Button variant="secondary" onClick={() => setDeferOpen(true)}>
                    Schieben
                  </Button>
                  <Button variant="primary" onClick={onAckCase}>
                    Fall quittieren
                  </Button>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {/* Modal: Schiebegrund auswählen */}
      <Modal
        open={deferOpen}
        title={`Fall ${selectedCaseId ?? ""} schieben`}
        onClose={() => setDeferOpen(false)}
      >
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
                    Hinweis: Im MVP sind das fixe Gründe. Später kann man hier eine interne Liste aus der Fachabteilung
                    pflegen.
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

      {toast ? (
        <Toast
          kind={toast.kind}
          message={toast.message}
          onClose={() => setToast(null)}
        />
      ) : null}
    </div>
  );
}
