/**
 * Datei: frontend/src/context/AuthContext.tsx
 * 
 * Zweck:
 * - Zentrale Auth-State-Verwaltung
 * - User, Station, Permissions
 * - Context API für globalen Zugriff
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface AuthState {
  userId: string;
  stationId: string;
  roles: string[];
  permissions: string[];
  breakGlass: boolean;
}

interface AuthContextType {
  auth: AuthState;
  setAuth: (auth: AuthState) => void;
  isAuthenticated: boolean;
  hasPermission: (permission: string) => boolean;
  hasRole: (role: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const LS_KEYS = {
  stationId: 'dashboard.stationId',
  userId: 'dashboard.userId',
};

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [auth, setAuthState] = useState<AuthState>({
    userId: localStorage.getItem(LS_KEYS.userId) || 'demo',
    stationId: localStorage.getItem(LS_KEYS.stationId) || 'ST01',
    roles: [],
    permissions: [],
    breakGlass: false,
  });

  // Persistiere Auth-State in localStorage
  const setAuth = (newAuth: AuthState) => {
    setAuthState(newAuth);
    localStorage.setItem(LS_KEYS.userId, newAuth.userId);
    localStorage.setItem(LS_KEYS.stationId, newAuth.stationId);
  };

  // Lade User-Info vom Backend
  useEffect(() => {
    fetch('/api/me', {
      headers: {
        'X-User-Id': auth.userId,
        'X-Station-Id': auth.stationId,
      },
    })
      .then((res) => res.json())
      .then((data) => {
        setAuthState((prev) => ({
          ...prev,
          roles: data.roles || [],
          permissions: data.permissions || [],
          breakGlass: data.break_glass || false,
        }));
      })
      .catch((err) => {
        console.error('Failed to load user info:', err);
      });
  }, [auth.userId, auth.stationId]);

  const isAuthenticated = !!auth.userId;

  const hasPermission = (permission: string): boolean => {
    return auth.permissions.includes(permission);
  };

  const hasRole = (role: string): boolean => {
    return auth.roles.includes(role);
  };

  const logout = () => {
    localStorage.removeItem(LS_KEYS.userId);
    localStorage.removeItem(LS_KEYS.stationId);
    setAuthState({
      userId: '',
      stationId: '',
      roles: [],
      permissions: [],
      breakGlass: false,
    });
  };

  return (
    <AuthContext.Provider
      value={{
        auth,
        setAuth,
        isAuthenticated,
        hasPermission,
        hasRole,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
