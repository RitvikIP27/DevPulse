import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { fetchAuthStatus, getToken, logout as clearToken, type AuthStatus } from "../api/client";

interface AuthValue {
  status: AuthStatus | null;
  loading: boolean;
  isAuthenticated: boolean;
  refresh: () => void;
  signOut: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * Resolves whether the user may see the app.
 *
 * When the server reports auth is not required the app renders immediately —
 * a local single-user install should not be forced through a login it does not
 * need. When auth IS required, a token must be present.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasToken, setHasToken] = useState(() => getToken() !== null);

  const refresh = useCallback(() => {
    setHasToken(getToken() !== null);
    setLoading(true);
    fetchAuthStatus()
      .then(setStatus)
      // If status itself cannot be reached, assume auth is required rather than
      // letting the app render as though it were open.
      .catch(() => setStatus({ auth_required: true, has_users: true }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(refresh, [refresh]);

  const signOut = useCallback(() => {
    clearToken();
    setHasToken(false);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        status,
        loading,
        isAuthenticated: status ? !status.auth_required || hasToken : false,
        refresh,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
