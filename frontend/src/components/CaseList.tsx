/**
 * Datei: frontend/src/components/CaseList.tsx
 * 
 * Zweck:
 * - Liste aller Cases
 * - Severity-basierte Sortierung
 * - Click-Handler für Details
 */

import { useCases } from '../context/CasesContext';
import type { CaseSummary, Severity } from '../types';
import './CaseList.css';

function severityColor(severity: Severity): string {
  switch (severity) {
    case 'CRITICAL':
      return '#ffe5e5';
    case 'WARN':
      return '#fff6d6';
    default:
      return '#e8f5e9';
  }
}

function severityIcon(severity: Severity): string {
  switch (severity) {
    case 'CRITICAL':
      return '🔴';
    case 'WARN':
      return '🟡';
    default:
      return '🟢';
  }
}

export function CaseList() {
  const { cases, loading, error, selectedCaseId, selectCase, loadCaseDetail } = useCases();

  const handleCaseClick = async (caseItem: CaseSummary) => {
    if (selectedCaseId === caseItem.case_id) {
      // Deselect
      selectCase(null);
    } else {
      // Select und Details laden
      selectCase(caseItem.case_id);
      await loadCaseDetail(caseItem.case_id);
    }
  };

  if (loading) {
    return (
      <div className="case-list-loading">
        <div className="spinner">Lade Fälle...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="case-list-error">
        <p>❌ Fehler beim Laden: {error}</p>
      </div>
    );
  }

  if (cases.length === 0) {
    return (
      <div className="case-list-empty">
        <p>Keine Fälle gefunden</p>
      </div>
    );
  }

  return (
    <div className="case-list">
      {cases.map((caseItem) => (
        <div
          key={caseItem.case_id}
          className={`case-card ${selectedCaseId === caseItem.case_id ? 'selected' : ''}`}
          style={{ backgroundColor: severityColor(caseItem.worst_severity) }}
          onClick={() => handleCaseClick(caseItem)}
        >
          <div className="case-header">
            <span className="severity-icon">
              {severityIcon(caseItem.worst_severity)}
            </span>
            <strong>{caseItem.case_id}</strong>
            {caseItem.all_acked && (
              <span className="acked-badge" title="Alle Meldungen quittiert">
                ✓
              </span>
            )}
          </div>
          
          <div className="case-info">
            <div>Eintritt: {caseItem.admission_date}</div>
            {caseItem.discharge_date && (
              <div>Austritt: {caseItem.discharge_date}</div>
            )}
          </div>
          
          <div className="case-stats">
            <span className="alert-count">
              {caseItem.alert_count} {caseItem.alert_count === 1 ? 'Meldung' : 'Meldungen'}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
