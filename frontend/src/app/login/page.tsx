"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/auth-context";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-background bg-dotted px-4 py-10">
      <div className="absolute inset-x-0 top-0 h-72 bg-gradient-to-b from-primary/[0.06] to-transparent pointer-events-none" aria-hidden />

      <div className="relative w-full max-w-[400px]">
        {/* Brand */}
        <div className="flex flex-col items-center text-center mb-7">
          <span className="inline-flex size-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-md mb-4">
            <span className="text-sm font-bold tracking-tight">B&amp;R</span>
          </span>
          <h1 className="text-xl font-semibold tracking-tight text-foreground">
            B&amp;R Food Services
          </h1>
          <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground mt-1">
            Operations Portal
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-card/95 backdrop-blur-sm shadow-xl shadow-foreground/5 p-7">
          <div className="mb-5">
            <h2 className="text-base font-semibold text-foreground">Sign in</h2>
            <p className="text-xs text-muted-foreground mt-0.5">
              Welcome back. Enter your credentials to continue.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-xs font-medium text-foreground">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
                placeholder="you@brfoods.com"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="text-xs font-medium text-foreground">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" size="lg" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>

        <p className="mt-5 text-center text-[11px] text-muted-foreground">
          Secured by JWT · All activity is audit-logged
        </p>
      </div>
    </div>
  );
}
