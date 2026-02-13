/**
 * Datei: frontend/src/context/CasesContext.tsx
 * 
 * Zweck:
 * - Zentrale Case-State-Verwaltung
 * - Cases laden, filtern, sortieren
 * - Detail-State
 */

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { CaseSummary, CaseDetail } from '../types';

interface CasesContextType {
  cases: CaseSummary[];
  loading: boolean;
  error: string | null;
  selectedCaseId: string | null;
  caseDetail: CaseDetail | null;
  detailLoading: boolean;
  
  loadCases: () => Promise<void>;
  selectCase: (caseId: string | null) => void;
  loadCaseDetail: (caseId: string) => Promise<void>;
  refreshCase: (caseId: string) => Promise<void>;
}

const CasesContext = createContext<CasesContextType | undefined>(undefined);

interface CasesProviderProps {
  children: ReactNode;
}

export function CasesProvider({ children }: CasesProviderProps) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadCases = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/cases');
      if (!response.ok) {
        throw new Error('Failed to load cases');
      }
      const data = await response.json();
      setCases(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  const selectCase = useCallback((caseId: string | null) => {
    setSelectedCaseId(caseId);
    if (!caseId) {
      setCaseDetail(null);
    }
  }, []);

  const loadCaseDetail = useCallback(async (caseId: string) => {
    setDetailLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`/api/cases/${caseId}`);
      if (!response.ok) {
        if (response.status === 404) {
          // Case nicht gefunden - Selection aufheben
          setSelectedCaseId(null);
          setCaseDetail(null);
          throw new Error('Case not found');
        }
        throw new Error('Failed to load case detail');
      }
      const data = await response.json();
      setCaseDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setCaseDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const refreshCase = useCallback(async (caseId: string) => {
    // Refresh sowohl Liste als auch Detail
    await Promise.all([
      loadCases(),
      loadCaseDetail(caseId),
    ]);
  }, [loadCases, loadCaseDetail]);

  return (
    <CasesContext.Provider
      value={{
        cases,
        loading,
        error,
        selectedCaseId,
        caseDetail,
        detailLoading,
        loadCases,
        selectCase,
        loadCaseDetail,
        refreshCase,
      }}
    >
      {children}
    </CasesContext.Provider>
  );
}

export function useCases() {
  const context = useContext(CasesContext);
  if (!context) {
    throw new Error('useCases must be used within CasesProvider');
  }
  return context;
}
