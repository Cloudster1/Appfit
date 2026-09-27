import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, type ReactNode } from "react";

import { api, UNAUTHORIZED_EVENT, unwrap } from "../api/client";
import { keys, useMe, type Role, type UserOut } from "../api/hooks";

const ROLE_RANK: Record<Role, number> = { viewer: 1, editor: 2, admin: 3 };

type AuthState = {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<UserOut>;
  logout: () => Promise<void>;
  hasRole: (min: Role) => boolean;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useMe();
  const user = me.data ?? null;

  useEffect(() => {
    const onUnauthorized = () => qc.setQueryData(keys.me, null);
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [qc]);

  // Drop cached data of the previous session but keep the observed "me" query instance alive.
  const resetSession = useCallback(
    (next: UserOut | null) => {
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== keys.me[0] });
      qc.setQueryData(keys.me, next);
    },
    [qc],
  );

  const login = useCallback(
    async (email: string, password: string) => {
      const res = unwrap(await api.POST("/api/auth/login", { body: { email, password } }));
      resetSession(res.user);
      return res.user;
    },
    [resetSession],
  );

  const logout = useCallback(async () => {
    await api.POST("/api/auth/logout");
    resetSession(null);
  }, [resetSession]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading: me.isPending,
      login,
      logout,
      hasRole: (min) => Boolean(user && ROLE_RANK[user.role] >= ROLE_RANK[min]),
    }),
    [user, me.isPending, login, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
