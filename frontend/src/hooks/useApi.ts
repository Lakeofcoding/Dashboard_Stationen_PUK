/**
 * Datei: frontend/src/hooks/useApi.ts
 * 
 * Zweck:
 * - Custom Hook für API-Calls
 * - Automatisches Auth-Header-Handling
 * - CSRF-Token-Handling
 * - Error-Handling
 */

import { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';

interface UseApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: any;
  onSuccess?: (data: any) => void;
  onError?: (error: Error) => void;
}

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  execute: (options?: UseApiOptions) => Promise<T | null>;
  reset: () => void;
}

export function useApi<T = any>(
  initialUrl: string,
  initialOptions?: UseApiOptions
): UseApiResult<T> {
  const { auth } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const execute = useCallback(async (
    options?: UseApiOptions
  ): Promise<T | null> => {
    const mergedOptions = { ...initialOptions, ...options };
    const method = mergedOptions.method || 'GET';
    const body = mergedOptions.body;

    setLoading(true);
    setError(null);

    try {
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
        'X-User-Id': auth.userId,
        'X-Station-Id': auth.stationId,
      };

      // CSRF-Token für mutating requests
      if (method !== 'GET') {
        const csrfToken = getCsrfToken();
        if (csrfToken) {
          headers['X-CSRF-Token'] = csrfToken;
        }
      }

      const response = await fetch(initialUrl, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      const responseData = await response.json();
      setData(responseData);

      if (mergedOptions.onSuccess) {
        mergedOptions.onSuccess(responseData);
      }

      return responseData;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      setError(error);

      if (mergedOptions.onError) {
        mergedOptions.onError(error);
      }

      return null;
    } finally {
      setLoading(false);
    }
  }, [initialUrl, initialOptions, auth]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    data,
    loading,
    error,
    execute,
    reset,
  };
}

/**
 * Helper: CSRF-Token aus Cookie holen
 */
function getCsrfToken(): string | null {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=');
    if (name === 'csrf_token') {
      return value;
    }
  }
  return null;
}
