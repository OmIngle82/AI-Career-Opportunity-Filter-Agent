"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  token: string | null;
  username: string | null;
  login: (token: string, username: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Load from local storage
    const storedToken = localStorage.getItem("token");
    const storedUsername = localStorage.getItem("username");
    
    if (storedToken && storedUsername) {
      setToken(storedToken);
      setUsername(storedUsername);
    }
    
    setIsLoading(false);
  }, []);

  useEffect(() => {
    // Route guard
    if (!isLoading) {
      const isAuthRoute = pathname === "/login" || pathname === "/register";
      const isAuthenticated = !!token;

      if (!isAuthenticated && !isAuthRoute) {
        router.push("/login");
      } else if (isAuthenticated && isAuthRoute) {
        router.push("/");
      }
    }
  }, [isLoading, token, pathname, router]);

  const login = (newToken: string, newUsername: string) => {
    localStorage.setItem("token", newToken);
    localStorage.setItem("username", newUsername);
    setToken(newToken);
    setUsername(newUsername);
    router.push("/");
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    setToken(null);
    setUsername(null);
    router.push("/login");
  };

  const isAuthenticated = !!token;

  if (isLoading) {
    return <div className="h-screen w-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">Loading...</div>;
  }

  return (
    <AuthContext.Provider value={{ token, username, login, logout, isAuthenticated, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
