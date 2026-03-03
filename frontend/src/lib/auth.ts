"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { api } from "./api-client";
import type { User, Tenant } from "@/types";

// Re-export for use in components
import React from "react";

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (data: {
    name: string;
    email: string;
    password: string;
    tenant_name: string;
    tenant_type: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    tenant: null,
    isAuthenticated: false,
    isLoading: true,
  });

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<{ user: User; tenant: Tenant }>("/api/auth/me");
      setState({
        user: data.user,
        tenant: data.tenant,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch {
      setState({
        user: null,
        tenant: null,
        isAuthenticated: false,
        isLoading: false,
      });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = async (email: string, password: string) => {
    const data = await api.post<{ token: string; user: User; tenant: Tenant }>(
      "/api/auth/login",
      { email, password }
    );
    setState({
      user: data.user,
      tenant: data.tenant,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const signup = async (data: {
    name: string;
    email: string;
    password: string;
    tenant_name: string;
    tenant_type: string;
  }) => {
    const result = await api.post<{ token: string; user: User; tenant: Tenant }>(
      "/api/auth/signup",
      data
    );
    setState({
      user: result.user,
      tenant: result.tenant,
      isAuthenticated: true,
      isLoading: false,
    });
  };

  const logout = async () => {
    await api.post("/api/auth/logout").catch(() => {});
    setState({
      user: null,
      tenant: null,
      isAuthenticated: false,
      isLoading: false,
    });
  };

  return React.createElement(
    AuthContext.Provider,
    { value: { ...state, login, signup, logout, refresh } },
    children
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
