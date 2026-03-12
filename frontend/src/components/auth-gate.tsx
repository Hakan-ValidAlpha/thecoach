"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL === undefined
  ? "http://localhost:8002"
  : process.env.NEXT_PUBLIC_API_URL;

export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"checking" | "authenticated" | "login">("checking");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/api/auth/check`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setState(d.authenticated ? "authenticated" : "login"))
      .catch(() => setState("authenticated")); // If auth endpoint doesn't exist, skip
  }, []);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ password }),
    });
    const data = await res.json();
    if (data.ok) {
      setState("authenticated");
    } else {
      setError("Wrong password");
    }
  }

  if (state === "checking") {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (state === "login") {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <form onSubmit={handleLogin} className="w-full max-w-xs space-y-4 px-4">
          <div className="text-center space-y-1">
            <h1 className="text-2xl font-bold text-primary">TheCoach</h1>
            <p className="text-sm text-muted-foreground">Enter password to continue</p>
          </div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoFocus
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <button
            type="submit"
            className="w-full rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Login
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
