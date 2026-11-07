"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { supabaseConfigured } from "@/lib/supabase";
import { useApp } from "./AppProvider";

/** Login is required before the test (thesis FR1). Unauthenticated visitors are sent to /masuk and
 *  brought back to the page they wanted afterwards. */
export function AuthGate({ children }: { children: ReactNode }) {
  const { user, authReady, t } = useApp();
  const router = useRouter();

  useEffect(() => {
    if (authReady && supabaseConfigured && !user) {
      const next = encodeURIComponent(window.location.pathname);
      router.push(`/masuk?next=${next}`);
    }
  }, [authReady, user, router]);

  if (!supabaseConfigured) return <p className="notice error">{t.supabase_missing}</p>;
  if (!authReady || !user) return <p className="loading">{t.login_required}</p>;
  return <>{children}</>;
}
